import random
import math
import os
import json
import threading
import pygame
import sys
import network as _netmod
import relay_server as _relay

_base = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(_base, "data", "game_settings.json")) as f:
    _cfg = json.load(f)

WIDTH             = _cfg["viewport"]["width"]
HEIGHT            = _cfg["viewport"]["height"]
player_size       = _cfg["player_size"]
maxhp1            = _cfg["default_maxhp"]
maxhp2            = _cfg["default_maxhp"]
speed             = _cfg["default_speed"]
DIFFICULTY        = _cfg["default_difficulty"]
ENERGY_MOVE_COST  = _cfg["energy"]["move_cost"]
ENERGY_REGEN_RATE = _cfg["energy"]["regen_rate"]
BAR_WIDTH         = _cfg["ui"]["bar_width"]
BAR_HEIGHT        = _cfg["ui"]["bar_height"]
ENERGY_BAR_HEIGHT = _cfg["ui"]["energy_bar_height"]
HUD_HEIGHT        = _cfg["ui"]["hud_height"]
MUSIC_VOLUME      = _cfg["music_volume"]
RELAY_HOST        = _cfg.get("relay_host", "127.0.0.1")
RELAY_PORT        = _cfg.get("relay_port", 5555)

def _load_player(filename):
    with open(os.path.join(_base, "data", filename)) as f:
        data = json.load(f)
    data["colors"] = {k: tuple(v) for k, v in data["colors"].items()}
    data["body"] = tuple(data["body"])
    return data

with open(os.path.join(_base, "data", "player_default.json")) as f:
    _default = json.load(f)
ATTACKS   = _default["attacks"]
P1_COLORS = {k: tuple(v) for k, v in _default["p1_colors"].items()}
P2_COLORS = {k: tuple(v) for k, v in _default["p2_colors"].items()}
P1_BODY   = tuple(_default["p1_body"])
P2_BODY   = tuple(_default["p2_body"])

CHARACTERS = [
    _load_player("player_rock.json"),
    _load_player("player_paper.json"),
    _load_player("player_scissors.json"),
]

class Player:
    def __init__(self, x, y, maxhp, attacks, MAX_ENERGY, size=40,):
        self.x = x
        self.y = y
        self.size = size

        self.maxhp = maxhp
        self.hp = maxhp

        self.maxenergy = MAX_ENERGY
        self.energy = MAX_ENERGY

        self.attacks = attacks

        self.dir = (1, 0)

        self.attack = None
        self.cooldown = 0
        self.anim = 0
        self.hit = False

    @property
    def rect(self):
        return pygame.Rect(self.x, self.y, self.size, self.size)

    def move(self, dx, dy, speed, width, height, no_cost=False):
        if not no_cost and self.energy <= 0:
            return

        self.x += dx * speed
        self.y += dy * speed
        self.dir = (dx, dy)

        self.x = max(0, min(self.x, width - self.size))
        self.y = max(HUD_HEIGHT, min(self.y, height - self.size))

        if not no_cost:
            self.energy = max(0, self.energy - ENERGY_MOVE_COST)

    def start_attack(self, name):
        cost = self.attacks[name].get("energy", 0)
        if self.cooldown == 0 and self.energy >= cost:
            self.attack = name
            self.anim = self.attacks[name]["frames"]
            self.cooldown = self.attacks[name]["cooldown"]
            self.hit = False
            self.energy = max(0, self.energy - cost)

    def update_attack_timers(self):
        if self.cooldown > 0:
            self.cooldown -= 1

        if self.anim > 0:
            self.anim -= 1
            if self.anim == 0:
                self.attack = None

    def dash_move(self, width, height):
        if self.attack == "dash" and self.anim > 0:
            dx, dy = self.dir
            speed = self.attacks["dash"]["speed"]
            self.move(dx, dy, speed, width, height, no_cost=True)

    def update_energy(self):
        self.energy = min(self.maxenergy, self.energy + ENERGY_REGEN_RATE)

    def get_hitbox(self):
        if not self.attack:
            return None

        atk = self.attacks[self.attack]
        dx, dy = self.dir

        radius = atk["radius"]
        half_w = int(radius * math.sin(math.radians(atk["degree"] / 2)))

        cx = self.x + self.size // 2
        cy = self.y + self.size // 2

        # RIGHT
        if dx == 1:
            return pygame.Rect(cx, cy - half_w, radius, half_w * 2)

        # LEFT
        if dx == -1:
            return pygame.Rect(cx - radius, cy - half_w, radius, half_w * 2)

        # DOWN
        if dy == 1:
            return pygame.Rect(cx - half_w, cy, half_w * 2, radius)

        # UP
        if dy == -1:
            return pygame.Rect(cx - half_w, cy - radius, half_w * 2, radius)
def draw_arrow(screen, rect, direction, color):
    dx, dy = direction
    size = 6

    cx, cy = rect.center

    # Move arrow outside the player
    offset = rect.width // 2 + 10
    ox = cx + dx * offset
    oy = cy + dy * offset

    # Arrow tip
    tip = (ox + dx * size * 2, oy + dy * size * 2)

    if dx != 0:  # left / right
        left = (ox, oy - size)
        right = (ox, oy + size)
    else:  # up / down
        left = (ox - size, oy)
        right = (ox + size, oy)

    pygame.draw.polygon(screen, color, [tip, left, right])


def draw_sector(screen, color, cx, cy, radius, center_angle_deg, spread_deg, steps=20):
    half = spread_deg / 2
    points = [(cx, cy)]
    for i in range(steps + 1):
        angle = math.radians(center_angle_deg - half + i * spread_deg / steps)
        points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    pygame.draw.polygon(screen, color, points)


def draw_online_hud(screen, players, chars, teams):
    """Draw compact HP/energy bars for all online players across the top."""
    n      = len(players)
    margin = 20
    gap    = 10
    bar_w  = (WIDTH - 2 * margin - (n - 1) * gap) // n
    bar_h  = 14
    nrg_h  = 8

    hud_surf = pygame.Surface((WIDTH, HUD_HEIGHT), pygame.SRCALPHA)
    hud_surf.fill((0, 0, 0, 180))
    screen.blit(hud_surf, (0, 0))

    TEAM_HP_COLORS = [(50, 255, 50), (50, 200, 255), (255, 180, 50), (220, 50, 255)]
    font_hud = pygame.font.SysFont(None, 22)

    for i, p in enumerate(players):
        x       = margin + i * (bar_w + gap)
        hp_rat  = max(0.0, p.hp / p.maxhp)
        nrg_rat = p.energy / p.maxenergy

        hp_color = (TEAM_HP_COLORS[teams[i] % len(TEAM_HP_COLORS)]
                    if teams else (50, 255, 50))

        pygame.draw.rect(screen, (80, 80, 80),  (x, 20, bar_w, bar_h))
        pygame.draw.rect(screen, hp_color,       (x, 20, int(bar_w * hp_rat), bar_h))
        pygame.draw.rect(screen, (50, 50, 50),  (x, 20 + bar_h + 3, bar_w, nrg_h))
        pygame.draw.rect(screen, (255, 200, 0), (x, 20 + bar_h + 3, int(bar_w * nrg_rat), nrg_h))

        label = f"P{i + 1}" + (f" T{teams[i] + 1}" if teams else "")
        lbl   = font_hud.render(label, True, chars[i]["body"])
        screen.blit(lbl, (x, 20 + bar_h + 3 + nrg_h + 2))


def online_lobby_and_select(screen, clock):
    """Online lobby + character select.
    Returns (net, my_pid, chars_list, teams, max_players) or None if cancelled."""
    font_big   = pygame.font.SysFont(None, 72)
    font_mid   = pygame.font.SysFont(None, 48)
    font_small = pygame.font.SysFont(None, 30)

    # phase: menu | host_config | host_wait | join_input | join_wait | char_select | waiting_char
    phase          = "menu"
    net            = None
    room_code      = None
    code_input     = ""
    status         = ""
    error          = None
    max_players    = 2
    teams_mode     = False
    my_char_index  = 0
    chars_received = {}   # {pid: char_index}

    net_ready = threading.Event()
    net_error = [None]

    def do_host(mp):
        nonlocal net, room_code
        try:
            relay_bound = threading.Event()
            threading.Thread(target=_relay.start, args=(RELAY_PORT, relay_bound), daemon=True).start()
            if not relay_bound.wait(timeout=5):
                net_error[0] = "Relay server failed to start"
                return
            n = _netmod.Network('127.0.0.1', RELAY_PORT)
            code = n.request_host(mp)
            if code is None:
                net_error[0] = n.error or "Failed to get room code"
                return
            room_code = code
            if n.wait_ready():
                net = n
                net_ready.set()
            else:
                net_error[0] = n.error or "Players didn't connect in time"
        except Exception as exc:
            net_error[0] = str(exc)

    def do_join(code):
        nonlocal net
        try:
            n = _netmod.Network(RELAY_HOST, RELAY_PORT)
            if n.join(code):
                net = n
                net_ready.set()
            else:
                net_error[0] = n.error or "Failed to join room"
        except Exception as exc:
            net_error[0] = str(exc)

    while True:
        clock.tick(60)
        screen.fill((10, 10, 25))

        title = font_big.render("ONLINE MULTIPLAYER", True, (240, 240, 240))
        screen.blit(title, title.get_rect(center=(WIDTH // 2, 70)))

        if phase == "menu":
            h_s = font_mid.render("H  -  Host a game", True, (200, 200, 200))
            j_s = font_mid.render("J  -  Join a game", True, (200, 200, 200))
            r_s = font_small.render(
                f"Relay: {RELAY_HOST}:{RELAY_PORT}  (edit relay_host/relay_port in game_settings.json)",
                True, (90, 90, 90))
            screen.blit(h_s, h_s.get_rect(center=(WIDTH // 2, 220)))
            screen.blit(j_s, j_s.get_rect(center=(WIDTH // 2, 280)))
            screen.blit(r_s, r_s.get_rect(center=(WIDTH // 2, 390)))

        elif phase == "host_config":
            cfg1 = font_mid.render(f"Players:  2  /  4  /  6  (current: {max_players})", True, (200, 200, 200))
            cfg2 = font_mid.render(f"Teams:  {'ON' if teams_mode else 'OFF'}  (T to toggle)", True,
                                   (100, 255, 100) if teams_mode else (200, 200, 200))
            cfg3 = font_small.render("2 / 4 / 6  to change player count", True, (150, 150, 150))
            cfg4 = font_small.render("ENTER  to start hosting", True, (150, 150, 150))
            screen.blit(cfg1, cfg1.get_rect(center=(WIDTH // 2, 210)))
            screen.blit(cfg2, cfg2.get_rect(center=(WIDTH // 2, 265)))
            screen.blit(cfg3, cfg3.get_rect(center=(WIDTH // 2, 350)))
            screen.blit(cfg4, cfg4.get_rect(center=(WIDTH // 2, 385)))

        elif phase == "host_wait":
            if room_code:
                c_s   = font_big.render(room_code, True, (100, 255, 100))
                count = net.players_connected if net else 1
                cnt_s = font_small.render(f"{count} / {max_players} players connected", True, (255, 180, 50))
                sh_s  = font_small.render("Share this code with your players", True, (180, 180, 180))
                screen.blit(c_s,   c_s.get_rect(center=(WIDTH // 2, 200)))
                screen.blit(sh_s,  sh_s.get_rect(center=(WIDTH // 2, 270)))
                screen.blit(cnt_s, cnt_s.get_rect(center=(WIDTH // 2, 310)))
            else:
                conn_s = font_small.render("Connecting to relay server...", True, (180, 180, 180))
                screen.blit(conn_s, conn_s.get_rect(center=(WIDTH // 2, 220)))

        elif phase == "join_input":
            prompt = font_mid.render("Enter room code:", True, (200, 200, 200))
            inp_s  = font_big.render(code_input.ljust(6, "_"), True, (100, 255, 100))
            screen.blit(prompt, prompt.get_rect(center=(WIDTH // 2, 200)))
            screen.blit(inp_s,  inp_s.get_rect(center=(WIDTH // 2, 270)))
            if status:
                st_s = font_small.render(status, True, (255, 180, 50))
                screen.blit(st_s, st_s.get_rect(center=(WIDTH // 2, 360)))

        elif phase == "join_wait":
            wait_s = font_small.render("Connected! Waiting for host to start...", True, (255, 180, 50))
            screen.blit(wait_s, wait_s.get_rect(center=(WIDTH // 2, 250)))

        elif phase in ("char_select", "waiting_char"):
            instr = font_small.render("A / D  to choose   E  to lock in", True, (180, 180, 180))
            screen.blit(instr, instr.get_rect(center=(WIDTH // 2, 130)))

            char = CHARACTERS[my_char_index]
            box  = pygame.Rect(WIDTH // 2 - 175, 170, 350, 260)
            pygame.draw.rect(screen, (40, 40, 50), box, border_radius=12)
            pygame.draw.rect(screen, char["body"], (box.x + 30, box.y + 70, 80, 80))
            nm_s = font_mid.render(char["name"], True, (255, 255, 255))
            screen.blit(nm_s, (box.x + 130, box.y + 70))
            st_s = font_small.render(f"HP: {char['maxhp']}   SPEED: {char['speed']}", True, (200, 200, 200))
            screen.blit(st_s, (box.x + 130, box.y + 130))
            lk_s = font_small.render(
                "NOT LOCKED" if phase == "char_select" else
                f"LOCKED  ({len(chars_received)}/{max_players} ready)",
                True, (255, 180, 80) if phase == "char_select" else (100, 255, 100))
            screen.blit(lk_s, (box.x + 130, box.y + 170))

        if error:
            err_s = font_small.render(f"Error: {error}", True, (255, 80, 80))
            screen.blit(err_s, err_s.get_rect(center=(WIDTH // 2, 490)))

        esc_s = font_small.render("ESC  -  Back", True, (80, 80, 80))
        screen.blit(esc_s, esc_s.get_rect(center=(WIDTH // 2, 560)))

        # Network ready → go to char select
        if net_ready.is_set() and phase in ("host_wait", "join_wait"):
            net_ready.clear()
            max_players = net.max_players or max_players
            phase = "char_select"

        # Background thread errors
        if net_error[0] and phase in ("host_wait", "join_input", "join_wait"):
            error = net_error[0]
            net_error[0] = None
            phase = "menu"
            net = None
            room_code = None

        # In waiting_char: collect char messages from all other players
        if phase == "waiting_char" and net:
            for upd in net.get_updates():
                if upd.get("type") == "char":
                    chars_received[upd["pid"]] = upd["index"]
            if len(chars_received) == max_players:
                # Build ordered char list and teams
                chars_list = [CHARACTERS[chars_received[i]] for i in range(max_players)]
                teams      = [i % 2 for i in range(max_players)] if teams_mode else []
                return net, net.player_id, chars_list, teams, max_players

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                if net: net.close()
                return None

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if net: net.close()
                    return None

                if phase == "menu":
                    if event.key == pygame.K_h:
                        phase = "host_config"
                        error = None
                    elif event.key == pygame.K_j:
                        phase      = "join_input"
                        error      = None
                        code_input = ""
                        status     = "Type the 6-character code, then press ENTER"

                elif phase == "host_config":
                    if event.key == pygame.K_2:
                        max_players = 2
                    elif event.key == pygame.K_4:
                        max_players = 4
                    elif event.key == pygame.K_6:
                        max_players = 6
                    elif event.key == pygame.K_t:
                        teams_mode = not teams_mode
                    elif event.key == pygame.K_RETURN:
                        phase = "host_wait"
                        error = None
                        threading.Thread(target=do_host, args=(max_players,), daemon=True).start()

                elif phase == "join_input":
                    if event.key == pygame.K_RETURN and len(code_input) == 6:
                        status = "Connecting..."
                        phase  = "join_wait"
                        threading.Thread(target=do_join, args=(code_input,), daemon=True).start()
                    elif event.key == pygame.K_BACKSPACE:
                        code_input = code_input[:-1]
                        error = None
                        net_error[0] = None
                    else:
                        ch = event.unicode.upper()
                        if ch in 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789' and len(code_input) < 6:
                            code_input += ch

                elif phase == "char_select":
                    if event.key == pygame.K_a:
                        my_char_index = (my_char_index - 1) % len(CHARACTERS)
                    elif event.key == pygame.K_d:
                        my_char_index = (my_char_index + 1) % len(CHARACTERS)
                    elif event.key == pygame.K_e:
                        phase = "waiting_char"
                        chars_received[net.player_id] = my_char_index
                        net.send({"type": "char", "pid": net.player_id, "index": my_char_index})
                        # Drain any already-buffered char messages
                        for upd in net.get_updates():
                            if upd.get("type") == "char":
                                chars_received[upd["pid"]] = upd["index"]

        pygame.display.flip()

    return None


def main_menu(screen, clock):
    font_title = pygame.font.SysFont(None, 96)
    font_hint = pygame.font.SysFont(None, 36)
    font_small = pygame.font.SysFont(None, 28)

    difficulties = ["baby","easy", "hard", "unbeatable", "og"]
    diff_index = 0

    while True:
        clock.tick(60)
        screen.fill((20, 20, 20))

        title = font_title.render("PYGAME FIGHTING", True, (255, 255, 255))
        hint1 = font_hint.render("ENTER  - Local Multiplayer", True, (200, 200, 200))
        hint2 = font_hint.render("RSHIFT - Singleplayer", True, (200, 200, 200))
        hint_o = font_hint.render("O      - Online Multiplayer", True, (100, 220, 255))
        hint3 = font_small.render("LEFT / RIGHT - Difficulty", True, (150, 150, 150))
        hint4 = font_small.render(
            f"Difficulty: {difficulties[diff_index].upper()}",
            True,
            (255, 180, 50)
        )

        screen.blit(title,  title.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 140)))
        screen.blit(hint1,  hint1.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 20)))
        screen.blit(hint2,  hint2.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 25)))
        screen.blit(hint_o, hint_o.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 70)))
        screen.blit(hint3,  hint3.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 130)))
        screen.blit(hint4,  hint4.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 165)))

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit", None

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_LEFT:
                    diff_index = (diff_index - 1) % len(difficulties)

                if event.key == pygame.K_RIGHT:
                    diff_index = (diff_index + 1) % len(difficulties)

                if event.key == pygame.K_RETURN:
                    return "start", difficulties[diff_index]

                if event.key == pygame.K_RSHIFT:
                    return "singleplayer", difficulties[diff_index]

                if event.key == pygame.K_o:
                    return "online", None

                if event.key == pygame.K_ESCAPE:
                    return "quit", None

        pygame.display.flip()

def character_select(screen, clock):
    font_title = pygame.font.SysFont(None, 72)
    font_big = pygame.font.SysFont(None, 54)
    font_small = pygame.font.SysFont(None, 28)

    p1_index = 0
    p2_index = 1
    p1_locked = False
    p2_locked = False

    while True:
        clock.tick(60)
        screen.fill((15, 15, 20))

        title = font_title.render("CHARACTER SELECT", True, (240, 240, 240))
        screen.blit(title, title.get_rect(center=(WIDTH // 2, 60)))

        # Instructions
        instr1 = font_small.render("P1: A/D to choose, E to lock", True, (180, 180, 180))
        instr2 = font_small.render("P2: LEFT/RIGHT to choose, / to lock", True, (180, 180, 180))
        instr3 = font_small.render("ESC to cancel", True, (140, 140, 140))
        screen.blit(instr1, (60, 110))
        screen.blit(instr2, (60, 140))
        screen.blit(instr3, (60, 170))

        # Display P1 / P2 selections
        p1_char = CHARACTERS[p1_index]
        p2_char = CHARACTERS[p2_index]

        left_box = pygame.Rect(100, 230, 350, 260)
        right_box = pygame.Rect(WIDTH - 450, 230, 350, 260)

        pygame.draw.rect(screen, (40, 40, 50), left_box, border_radius=12)
        pygame.draw.rect(screen, (40, 40, 50), right_box, border_radius=12)

        # P1
        pygame.draw.rect(screen, p1_char["body"], (left_box.x + 30, left_box.y + 70, 80, 80))
        p1_name = font_big.render(p1_char["name"], True, (255, 255, 255))
        screen.blit(p1_name, (left_box.x + 130, left_box.y + 70))

        p1_stats = font_small.render(f"HP: {p1_char['maxhp']}   SPEED: {p1_char['speed']}", True, (200, 200, 200))
        screen.blit(p1_stats, (left_box.x + 130, left_box.y + 130))

        p1_lock = font_small.render("LOCKED" if p1_locked else "NOT LOCKED", True, (100, 255, 100) if p1_locked else (255, 180, 80))
        screen.blit(p1_lock, (left_box.x + 130, left_box.y + 170))

        # P2
        pygame.draw.rect(screen, p2_char["body"], (right_box.x + 30, right_box.y + 70, 80, 80))
        p2_name = font_big.render(p2_char["name"], True, (255, 255, 255))
        screen.blit(p2_name, (right_box.x + 130, right_box.y + 70))

        p2_stats = font_small.render(f"HP: {p2_char['maxhp']}   SPEED: {p2_char['speed']}", True, (200, 200, 200))
        screen.blit(p2_stats, (right_box.x + 130, right_box.y + 130))

        p2_lock = font_small.render("LOCKED" if p2_locked else "NOT LOCKED", True, (100, 255, 100) if p2_locked else (255, 180, 80))
        screen.blit(p2_lock, (right_box.x + 130, right_box.y + 170))

        # If both locked, return chosen characters
        if p1_locked and p2_locked:
            return p1_char, p2_char

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None, None

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return None, None

                # P1 choose (A/D) and lock (E)
                if not p1_locked:
                    if event.key == pygame.K_a:
                        p1_index = (p1_index - 1) % len(CHARACTERS)
                    elif event.key == pygame.K_d:
                        p1_index = (p1_index + 1) % len(CHARACTERS)
                    elif event.key == pygame.K_e:
                        p1_locked = True

                # P2 choose (LEFT/RIGHT) and lock (/)
                if not p2_locked:
                    if event.key == pygame.K_LEFT:
                        p2_index = (p2_index - 1) % len(CHARACTERS)
                    elif event.key == pygame.K_RIGHT:
                        p2_index = (p2_index + 1) % len(CHARACTERS)
                    elif event.key == pygame.K_SLASH:
                        p2_locked = True

        pygame.display.flip()



# --- setup ---
pygame.init()

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Pygame fighting")

clock = pygame.time.Clock()

# --- player ---
font = pygame.font.SysFont(None, 80)
singleplayer = False
countdown = 120
win = False
running = True
winner_text = ""
p1_img = pygame.transform.scale(pygame.image.load(os.path.join(_base,"assets", "character1.png")).convert_alpha(), (player_size, player_size))
p2_img = pygame.transform.scale(pygame.image.load(os.path.join(_base,"assets", "character2.png")).convert_alpha(), (player_size, player_size))
bg_img = pygame.transform.scale(pygame.image.load(os.path.join(_base,"assets", "bg.png")).convert(), (WIDTH, HEIGHT))
pygame.mixer.music.load(os.path.join(_base,"assets", "bgm.mp3"))

AI_PRESETS = {
    "baby":{
        "think_delay": 30,
        "super_chance": 0,
        "dash_chance": 0.1,
        "retreat_chance": 0.6,
    },
    "easy": {
        "think_delay": 25,
        "super_chance": 0.03,
        "dash_chance": 0.18,
        "retreat_chance": 0.45,
    },
    "hard": {
        "think_delay": 14,
        "super_chance": 0.10,
        "dash_chance": 0.35,
        "retreat_chance": 0.20,
    },
    "unbeatable": {
        "think_delay": 4,
        "super_chance": 0.25,
        "dash_chance": 0.65,
        "retreat_chance": 0.0,
    },
    "og": {  # original AI
        "think_delay": 0,
        "super_chance": 1.0,
        "dash_chance": 1.0,
        "retreat_chance": 0.0,
    },
}

ai_think_timer = 0
energy = True

# Online mode state
online_mode        = False
net                = None
my_pid             = 0
online_players     = []   # Player objects indexed by pid
online_chars       = []   # char dicts indexed by pid
online_teams       = []   # teams[pid] = team number, [] means FFA
online_hit_reg     = {}   # {pid: bool} — did that attacker's swing already hit me?
online_player_speed = []  # speed per pid

# Start positions for each supported player count
ONLINE_START_POS = {
    2: [(50, 200), (820, 200)],
    4: [(50, 120), (820, 120), (50, 380), (820, 380)],
    6: [(50, 100), (420, 100), (780, 100), (50, 380), (420, 380), (780, 380)],
}

while running:

    # --- MENU ---
    menu_result, selected_difficulty = main_menu(screen, clock)

    if menu_result == "quit":
        break

    online_mode = False
    net = None

    if menu_result == "singleplayer":
        singleplayer = True
        DIFFICULTY = selected_difficulty

        # singleplayer uses your defaults
        p1 = Player(10, 10, maxhp1, ATTACKS,10000000, size=player_size)
        p2 = Player(800, 400, maxhp2, ATTACKS,10000000, size=player_size)

        p1_speed = speed
        p2_speed = speed
        P1_ATTACK_COLORS = P1_COLORS
        P2_ATTACK_COLORS = P2_COLORS
        p1_body_color = P1_BODY
        p2_body_color = P2_BODY

    elif menu_result == "online":
        result = online_lobby_and_select(screen, clock)
        if result is None:
            continue
        net, my_pid, online_chars, online_teams, _max_p = result
        singleplayer = False
        online_mode  = True
        online_hit_reg = {}

        start_pos    = ONLINE_START_POS[_max_p]
        online_players = []
        for _i in range(_max_p):
            _c   = online_chars[_i]
            _pos = start_pos[_i]
            online_players.append(Player(_pos[0], _pos[1], _c["maxhp"], _c["attacks"], 100, size=player_size))
        online_player_speed = [c["speed"] for c in online_chars]

        # p1/p2 are unused in online mode but must exist to avoid NameErrors
        # in the local draw section that's skipped by the if online_mode: branch
        p1 = online_players[0]
        p2 = online_players[1] if len(online_players) > 1 else online_players[0]
        maxhp1 = p1.maxhp
        maxhp2 = p2.maxhp

    else:  # "start" = local multiplayer
        singleplayer = False

        c1, c2 = character_select(screen, clock)
        if c1 is None:  # cancelled
            continue

        p1 = Player(10, 10, c1["maxhp"], c1["attacks"], 100, size=player_size)
        p2 = Player(800, 400, c2["maxhp"], c2["attacks"], 100, size=player_size)

        maxhp1 = c1["maxhp"]
        maxhp2 = c2["maxhp"]
        p1_speed = c1["speed"]
        p2_speed = c2["speed"]
        P1_ATTACK_COLORS = c1["colors"]
        P2_ATTACK_COLORS = c2["colors"]
        p1_body_color = c1["body"]
        p2_body_color = c2["body"]



    win = False
    winner_text = ""
    pygame.mixer.music.set_volume(MUSIC_VOLUME)
    pygame.mixer.music.play(-1)

    match_running = True

    # --- MATCH LOOP ---
    while match_running:

# --- game loop ---
        clock.tick(60)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                match_running = False

            # only when someone won, allow ENTER to go back to menu
            if win and event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    match_running = False

        if not win:
            keys = pygame.key.get_pressed()

            if online_mode:
                # ---- Online N-player input ----
                me       = online_players[my_pid]
                my_speed = online_player_speed[my_pid]

                if keys[pygame.K_a]: me.move(-1, 0, my_speed, WIDTH, HEIGHT)
                if keys[pygame.K_d]: me.move(1,  0, my_speed, WIDTH, HEIGHT)
                if keys[pygame.K_w]: me.move(0, -1, my_speed, WIDTH, HEIGHT)
                if keys[pygame.K_s]: me.move(0,  1, my_speed, WIDTH, HEIGHT)
                if keys[pygame.K_r]:   me.start_attack("super")
                elif keys[pygame.K_q]: me.start_attack("dash")
                elif keys[pygame.K_e]: me.start_attack("normal")

                # Receive all other players' states
                for upd in net.get_updates():
                    if upd.get("type") == "state":
                        pid = upd["pid"]
                        if 0 <= pid < len(online_players) and pid != my_pid:
                            p        = online_players[pid]
                            prev_atk = p.attack
                            p.x, p.y = upd["x"], upd["y"]
                            p.dir    = tuple(upd["dir"])
                            p.attack = upd["attack"]
                            p.anim   = upd["anim"]
                            p.cooldown = upd["cooldown"]
                            p.hp     = upd["hp"]
                            p.energy = upd["energy"]
                            if p.attack != prev_atk:
                                online_hit_reg[pid] = False

                # Send my state to everyone
                net.send({"type": "state", "pid": my_pid,
                          "x": me.x, "y": me.y, "dir": list(me.dir),
                          "attack": me.attack, "anim": me.anim,
                          "cooldown": me.cooldown, "hp": me.hp, "energy": me.energy})

                if not net.connected:
                    win = True
                    winner_text = "A PLAYER DISCONNECTED - press enter"
                    pygame.mixer.music.fadeout(2000)

                # Timers / energy / dash for all players
                for _p in online_players:
                    _p.update_attack_timers()
                    _p.update_energy()
                    _p.dash_move(WIDTH, HEIGHT)

            else:
                # ---- Local input ----
                if keys[pygame.K_a]: p1.move(-1, 0, p1_speed, WIDTH, HEIGHT)
                if keys[pygame.K_d]: p1.move(1,  0, p1_speed, WIDTH, HEIGHT)
                if keys[pygame.K_w]: p1.move(0, -1, p1_speed, WIDTH, HEIGHT)
                if keys[pygame.K_s]: p1.move(0,  1, p1_speed, WIDTH, HEIGHT)

                if singleplayer:
                    preset = AI_PRESETS[DIFFICULTY]
                    dx = p1.x - p2.x
                    dy = p1.y - p2.y
                    if abs(dx) > abs(dy):
                        p2.move(1 if dx > 0 else -1, 0, speed, WIDTH, HEIGHT)
                    else:
                        p2.move(0, 1 if dy > 0 else -1, speed, WIDTH, HEIGHT)
                    if DIFFICULTY != "og":
                        if abs(dx) + abs(dy) < 80 and random.random() < preset["retreat_chance"]:
                            p2.move(-p2.dir[0], -p2.dir[1], speed, WIDTH, HEIGHT)
                else:
                    if keys[pygame.K_LEFT]:  p2.move(-1, 0, p2_speed, WIDTH, HEIGHT)
                    if keys[pygame.K_RIGHT]: p2.move(1,  0, p2_speed, WIDTH, HEIGHT)
                    if keys[pygame.K_UP]:    p2.move(0, -1, p2_speed, WIDTH, HEIGHT)
                    if keys[pygame.K_DOWN]:  p2.move(0,  1, p2_speed, WIDTH, HEIGHT)

                if keys[pygame.K_r]:   p1.start_attack("super")
                elif keys[pygame.K_q]: p1.start_attack("dash")
                elif keys[pygame.K_e]: p1.start_attack("normal")

                if singleplayer:
                    preset = AI_PRESETS[DIFFICULTY]
                    dist   = abs(p1.x - p2.x) + abs(p1.y - p2.y)
                    if DIFFICULTY == "og":
                        if p2.cooldown == 0:
                            if dist < 60:   p2.start_attack("normal")
                            elif dist < 150: p2.start_attack("dash")
                            else:            p2.start_attack("super")
                    else:
                        ai_think_timer -= 1
                        if ai_think_timer <= 0 and p2.cooldown == 0:
                            ai_think_timer = preset["think_delay"]
                            roll = random.random()
                            if dist < 140 and roll < preset["super_chance"]:   p2.start_attack("super")
                            elif dist < 60:                                     p2.start_attack("normal")
                            elif dist < 180 and roll < preset["dash_chance"]:  p2.start_attack("dash")
                else:
                    if keys[pygame.K_PERIOD]:  p2.start_attack("super")
                    elif keys[pygame.K_RSHIFT]: p2.start_attack("dash")
                    elif keys[pygame.K_SLASH]:  p2.start_attack("normal")

                p1.update_attack_timers(); p2.update_attack_timers()
                if energy: p1.update_energy(); p2.update_energy()
                p1.dash_move(WIDTH, HEIGHT); p2.dash_move(WIDTH, HEIGHT)

        # ================================================================
        # --- draw ---
        # ================================================================
        screen.blit(bg_img, (0, 0))

        if online_mode:
            me   = online_players[my_pid]
            PUSH = 1.2

            # Collision push for every pair
            for _i in range(len(online_players)):
                for _j in range(_i + 1, len(online_players)):
                    _pa, _pb = online_players[_i], online_players[_j]
                    if _pa.rect.colliderect(_pb.rect):
                        _ov = _pa.rect.clip(_pb.rect)
                        if _ov.width < _ov.height:
                            if _pa.rect.centerx < _pb.rect.centerx:
                                _pa.x -= _ov.width * 0.5 * PUSH; _pb.x += _ov.width * 0.5 * PUSH
                            else:
                                _pa.x += _ov.width * 0.5 * PUSH; _pb.x -= _ov.width * 0.5 * PUSH
                        else:
                            if _pa.rect.centery < _pb.rect.centery:
                                _pa.y -= _ov.height * 0.5 * PUSH; _pb.y += _ov.height * 0.5 * PUSH
                            else:
                                _pa.y += _ov.height * 0.5 * PUSH; _pb.y -= _ov.height * 0.5 * PUSH
                        for _p in (_pa, _pb):
                            _p.x = max(0, min(_p.x, WIDTH - _p.size))
                            _p.y = max(HUD_HEIGHT, min(_p.y, HEIGHT - _p.size))

            # Draw every player
            for _pid, _p in enumerate(online_players):
                pygame.draw.rect(screen, online_chars[_pid]["body"], (_p.x, _p.y, _p.size, _p.size))
                _acol = (255, 100, 100) if _pid == my_pid else (100, 100, 255)
                draw_arrow(screen, _p.rect, _p.dir, _acol)
                _hb = _p.get_hitbox()
                if _hb:
                    _atk = _p.attacks[_p.attack]
                    _ang = math.degrees(math.atan2(_p.dir[1], _p.dir[0]))
                    draw_sector(screen, online_chars[_pid]["colors"][_p.attack],
                                _p.x + _p.size // 2, _p.y + _p.size // 2,
                                _atk["radius"], _ang, _atk["degree"])

            # Hit detection: I'm authoritative about my own HP
            for _pid, _att in enumerate(online_players):
                if _pid == my_pid:
                    continue
                if online_teams and online_teams[_pid] == online_teams[my_pid]:
                    continue  # no friendly fire
                _hb = _att.get_hitbox()
                if _hb and _hb.colliderect(me.rect) and not online_hit_reg.get(_pid, False):
                    me.hp -= _att.attacks[_att.attack]["dmg"]
                    online_hit_reg[_pid] = True
                if not _att.attack:
                    online_hit_reg[_pid] = False

            # Win overlay
            if win:
                _ov_s = pygame.Surface((WIDTH, HEIGHT)); _ov_s.fill((10, 10, 10))
                screen.blit(_ov_s, (0, 0))
                _ts = font.render(winner_text, True, (255, 255, 255))
                screen.blit(_ts, _ts.get_rect(center=(WIDTH // 2, HEIGHT // 2)))

            # HUD
            draw_online_hud(screen, online_players, online_chars, online_teams)

            # Win condition
            if not win:
                _alive = [_i for _i, _p in enumerate(online_players) if _p.hp > 0]
                if online_teams:
                    _alive_t = set(online_teams[_i] for _i in _alive)
                    if len(_alive_t) <= 1:
                        win = True
                        winner_text = (f"TEAM {_alive_t.pop() + 1} WINS - press enter"
                                       if _alive_t else "DRAW - press enter")
                        pygame.mixer.music.fadeout(2000)
                else:
                    if len(_alive) <= 1:
                        win = True
                        winner_text = (f"PLAYER {_alive[0] + 1} WINS - press enter"
                                       if _alive else "DRAW - press enter")
                        pygame.mixer.music.fadeout(2000)

        else:
            # ---- Local draw ----
            p1_rect = p1.rect
            p2_rect = p2.rect
            if p1.rect.colliderect(p2.rect):
                overlap = p1.rect.clip(p2.rect)
                PUSH = 1.2
                if overlap.width < overlap.height:
                    if p1.rect.centerx < p2.rect.centerx:
                        p1.x -= overlap.width * 0.5 * PUSH; p2.x += overlap.width * 0.5 * PUSH
                    else:
                        p1.x += overlap.width * 0.5 * PUSH; p2.x -= overlap.width * 0.5 * PUSH
                else:
                    if p1.rect.centery < p2.rect.centery:
                        p1.y -= overlap.height * 0.5 * PUSH; p2.y += overlap.height * 0.5 * PUSH
                    else:
                        p1.y += overlap.height * 0.5 * PUSH; p2.y -= overlap.height * 0.5 * PUSH
                p1.x = max(0, min(p1.x, WIDTH - p1.size))
                p1.y = max(HUD_HEIGHT, min(p1.y, HEIGHT - p1.size))
                p2.x = max(0, min(p2.x, WIDTH - p2.size))
                p2.y = max(HUD_HEIGHT, min(p2.y, HEIGHT - p2.size))

            screen.blit(p1_img, p1_rect)
            screen.blit(p2_img, p2_rect)
            draw_arrow(screen, p1.rect, p1.dir, (255, 100, 100))
            draw_arrow(screen, p2.rect, p2.dir, (100, 100, 255))
            hitbox1 = p1.get_hitbox()
            hitbox2 = p2.get_hitbox()
            if hitbox1:
                atk1   = p1.attacks[p1.attack]
                angle1 = math.degrees(math.atan2(p1.dir[1], p1.dir[0]))
                draw_sector(screen, P1_ATTACK_COLORS[p1.attack],
                            p1.x + p1.size // 2, p1.y + p1.size // 2,
                            atk1["radius"], angle1, atk1["degree"])
            if hitbox2:
                atk2   = p2.attacks[p2.attack]
                angle2 = math.degrees(math.atan2(p2.dir[1], p2.dir[0]))
                draw_sector(screen, P2_ATTACK_COLORS[p2.attack],
                            p2.x + p2.size // 2, p2.y + p2.size // 2,
                            atk2["radius"], angle2, atk2["degree"])

            if hitbox1 and hitbox1.colliderect(p2.rect) and not p1.hit:
                p2.hp -= ATTACKS[p1.attack]["dmg"]; p1.hit = True
            if hitbox2 and hitbox2.colliderect(p1.rect) and not p2.hit:
                p1.hp -= ATTACKS[p2.attack]["dmg"]; p2.hit = True

            p1hp = max(0, p1.hp)
            p2hp = max(0, p2.hp)
            if win:
                overlay = pygame.Surface((WIDTH, HEIGHT)); overlay.fill((10, 10, 10))
                screen.blit(overlay, (0, 0))
                text_surface = font.render(winner_text, True, (255, 255, 255))
                screen.blit(text_surface, text_surface.get_rect(center=(WIDTH // 2, HEIGHT // 2)))

            hud_surf = pygame.Surface((WIDTH, HUD_HEIGHT), pygame.SRCALPHA)
            hud_surf.fill((0, 0, 0, 180))
            screen.blit(hud_surf, (0, 0))

            pygame.draw.rect(screen, (100, 100, 100), (50, 30, BAR_WIDTH, BAR_HEIGHT))
            pygame.draw.rect(screen, (50, 255, 50),   (50, 30, BAR_WIDTH * (p1hp / maxhp1), BAR_HEIGHT))
            pygame.draw.rect(screen, (60, 60, 60),    (50, 57, BAR_WIDTH, ENERGY_BAR_HEIGHT))
            pygame.draw.rect(screen, (255, 200, 0),   (50, 57, BAR_WIDTH * (p1.energy / p1.maxenergy), ENERGY_BAR_HEIGHT))

            pygame.draw.rect(screen, (100, 100, 100), (WIDTH - 350, 30, BAR_WIDTH, BAR_HEIGHT))
            pygame.draw.rect(screen, (50, 255, 50),   (WIDTH - 350, 30, BAR_WIDTH * (p2hp / maxhp2), BAR_HEIGHT))
            pygame.draw.rect(screen, (60, 60, 60),    (WIDTH - 350, 57, BAR_WIDTH, ENERGY_BAR_HEIGHT))
            pygame.draw.rect(screen, (255, 200, 0),   (WIDTH - 350, 57, BAR_WIDTH * (p2.energy / p2.maxenergy), ENERGY_BAR_HEIGHT))

            if not win:
                if p1hp <= 0:
                    win = True; winner_text = "PLAYER 2 WINS - press enter"
                    pygame.mixer.music.fadeout(2000)
                elif p2hp <= 0:
                    win = True; winner_text = "PLAYER 1 WINS - press enter"
                    pygame.mixer.music.fadeout(2000)

        pygame.display.flip()

    # Clean up network connection after match ends
    if online_mode and net:
        net.close()
    net         = None
    online_mode = False
    online_players.clear()
    online_chars.clear()
    online_teams.clear()
    online_hit_reg.clear()

# Player 1 attack animation


# --- quit ---
pygame.display.quit()
pygame.quit()
sys.exit()

