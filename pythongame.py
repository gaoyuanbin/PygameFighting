import random
import math
import os
import json

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
        hint1 = font_hint.render("ENTER  - Multiplayer", True, (200, 200, 200))
        hint2 = font_hint.render("RSHIFT - Singleplayer", True, (200, 200, 200))
        hint3 = font_small.render("LEFT / RIGHT - Difficulty", True, (150, 150, 150))
        hint4 = font_small.render(
            f"Difficulty: {difficulties[diff_index].upper()}",
            True,
            (255, 180, 50)
        )

        screen.blit(title, title.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 120)))
        screen.blit(hint1, hint1.get_rect(center=(WIDTH // 2, HEIGHT // 2)))
        screen.blit(hint2, hint2.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 40)))
        screen.blit(hint3, hint3.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 100)))
        screen.blit(hint4, hint4.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 140)))

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

import pygame
import sys

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
bg_img = pygame.transform.scale(pygame.image.load(os.path.join(_base, "bg.png")).convert(), (WIDTH, HEIGHT))
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

while running:

    # --- MENU ---
    menu_result, selected_difficulty = main_menu(screen, clock)

    if menu_result == "quit":
        break

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

    else:
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

            # --- input ---
            # Player 1
            if keys[pygame.K_a]:
                p1.move(-1, 0, p1_speed, WIDTH, HEIGHT)
            if keys[pygame.K_d]:
                p1.move(1, 0, p1_speed, WIDTH, HEIGHT)
            if keys[pygame.K_w]:
                p1.move(0, -1, p1_speed, WIDTH, HEIGHT)
            if keys[pygame.K_s]:
                p1.move(0, 1, p1_speed, WIDTH, HEIGHT)

            # Player 2
            if singleplayer:
                preset = AI_PRESETS[DIFFICULTY]

                dx = p1.x - p2.x
                dy = p1.y - p2.y

                if abs(dx) > abs(dy):
                    direction = 1 if dx > 0 else -1
                    p2.move(direction, 0, speed, WIDTH, HEIGHT)
                else:
                    direction = 1 if dy > 0 else -1
                    p2.move(0, direction, speed, WIDTH, HEIGHT)

                # retreat (not OG)
                if DIFFICULTY != "og":
                    if abs(dx) + abs(dy) < 80 and random.random() < preset["retreat_chance"]:
                        p2.move(-p2.dir[0], -p2.dir[1], speed, WIDTH, HEIGHT)
            else:
                # Player 2 (human)
                if keys[pygame.K_LEFT]:
                    p2.move(-1, 0, p2_speed, WIDTH, HEIGHT)
                if keys[pygame.K_RIGHT]:
                    p2.move(1, 0, p2_speed, WIDTH, HEIGHT)
                if keys[pygame.K_UP]:
                    p2.move(0, -1, p2_speed, WIDTH, HEIGHT)
                if keys[pygame.K_DOWN]:
                    p2.move(0, 1, p2_speed, WIDTH, HEIGHT)

            # Player 1 attacks
            if keys[pygame.K_r]:
                p1.start_attack("super")
            elif keys[pygame.K_q]:
                p1.start_attack("dash")
            elif keys[pygame.K_e]:
                p1.start_attack("normal")

            # Player 2 attacks
            if singleplayer:
                preset = AI_PRESETS[DIFFICULTY]
                dist = abs(p1.x - p2.x) + abs(p1.y - p2.y)

                if DIFFICULTY == "og":
                    if p2.cooldown == 0:
                        if dist < 60:
                            p2.start_attack("normal")
                        elif dist < 150:
                            p2.start_attack("dash")
                        else:
                            p2.start_attack("super")
                else:
                    ai_think_timer -= 1

                    if ai_think_timer <= 0 and p2.cooldown == 0:
                        ai_think_timer = preset["think_delay"]
                        roll = random.random()

                        if dist < 140 and roll < preset["super_chance"]:
                            p2.start_attack("super")
                        elif dist < 60:
                            p2.start_attack("normal")
                        elif dist < 180 and roll < preset["dash_chance"]:
                            p2.start_attack("dash")

            else:
                if keys[pygame.K_PERIOD]:
                    p2.start_attack("super")
                elif keys[pygame.K_RSHIFT]:
                    p2.start_attack("dash")
                elif keys[pygame.K_SLASH]:
                    p2.start_attack("normal")

            # Update attack timers and energy
            p1.update_attack_timers()
            p2.update_attack_timers()
            if energy:
                p1.update_energy()
                p2.update_energy()

            # Dash movement
            p1.dash_move(WIDTH, HEIGHT)
            p2.dash_move(WIDTH, HEIGHT)


        # --- draw ---
        screen.blit(bg_img, (0, 0))
        p1_rect = p1.rect
        p2_rect = p2.rect
        if p1.rect.colliderect(p2.rect):
            overlap = p1.rect.clip(p2.rect)
            PUSH = 1.2

            if overlap.width < overlap.height:
                if p1.rect.centerx < p2.rect.centerx:
                    p1.x -= overlap.width * 0.5 * PUSH
                    p2.x += overlap.width * 0.5 * PUSH
                else:
                    p1.x += overlap.width * 0.5 * PUSH
                    p2.x -= overlap.width * 0.5 * PUSH
            else:
                if p1.rect.centery < p2.rect.centery:
                    p1.y -= overlap.height * 0.5 * PUSH
                    p2.y += overlap.height * 0.5 * PUSH
                else:
                    p1.y += overlap.height * 0.5 * PUSH
                    p2.y -= overlap.height * 0.5 * PUSH

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
            atk1 = p1.attacks[p1.attack]
            angle1 = math.degrees(math.atan2(p1.dir[1], p1.dir[0]))
            draw_sector(screen, P1_ATTACK_COLORS[p1.attack],
                        p1.x + p1.size // 2, p1.y + p1.size // 2,
                        atk1["radius"], angle1, atk1["degree"])
        if hitbox2:
            atk2 = p2.attacks[p2.attack]
            angle2 = math.degrees(math.atan2(p2.dir[1], p2.dir[0]))
            draw_sector(screen, P2_ATTACK_COLORS[p2.attack],
                        p2.x + p2.size // 2, p2.y + p2.size // 2,
                        atk2["radius"], angle2, atk2["degree"])

        if hitbox1 and hitbox1.colliderect(p2.rect) and not p1.hit:
            p2.hp -= ATTACKS[p1.attack]["dmg"]
            p1.hit = True

        if hitbox2 and hitbox2.colliderect(p1.rect) and not p2.hit:
            p1.hp -= ATTACKS[p2.attack]["dmg"]
            p2.hit = True

        p1hp = max(0, p1.hp)
        p2hp = max(0, p2.hp)
        if win:
            overlay = pygame.Surface((WIDTH, HEIGHT))
            overlay.fill((10,10,10))
            screen.blit(overlay, (0, 0))

            text_surface = font.render(winner_text, True, (255, 255, 255))
            text_rect = text_surface.get_rect(center=(WIDTH // 2, HEIGHT // 2))
            screen.blit(text_surface, text_rect)

        # HUD panel
        hud_surf = pygame.Surface((WIDTH, HUD_HEIGHT), pygame.SRCALPHA)
        hud_surf.fill((0, 0, 0, 180))
        screen.blit(hud_surf, (0, 0))

        # Player 1 HP bar
        pygame.draw.rect(screen, (100, 100, 100), (50, 30, BAR_WIDTH, BAR_HEIGHT))
        pygame.draw.rect(
            screen,
            (50, 255, 50),
            (50, 30, BAR_WIDTH * (p1hp / maxhp1), BAR_HEIGHT)
        )

        # Player 1 energy bar
        pygame.draw.rect(screen, (60, 60, 60), (50, 57, BAR_WIDTH, ENERGY_BAR_HEIGHT))
        pygame.draw.rect(
            screen,
            (255, 200, 0),
            (50, 57, BAR_WIDTH * (p1.energy / p1.maxenergy), ENERGY_BAR_HEIGHT)
        )

        # Player 2 HP bar
        pygame.draw.rect(screen, (100, 100, 100), (WIDTH - 350, 30, BAR_WIDTH, BAR_HEIGHT))
        pygame.draw.rect(
            screen,
            (50, 255, 50),
            (WIDTH - 350, 30, BAR_WIDTH * (p2hp / maxhp2), BAR_HEIGHT)
        )

        # Player 2 energy bar
        pygame.draw.rect(screen, (60, 60, 60), (WIDTH - 350, 57, BAR_WIDTH, ENERGY_BAR_HEIGHT))
        pygame.draw.rect(
            screen,
            (255, 200, 0),
            (WIDTH - 350, 57, BAR_WIDTH * (p2.energy / p2.maxenergy), ENERGY_BAR_HEIGHT)
        )
        if not win:
            if p1hp <= 0:
                win = True
                winner_text = "PLAYER 2 WINS - press enter"
                pygame.mixer.music.fadeout(2000)
            elif p2hp <= 0:
                win = True
                winner_text = "PLAYER 1 WINS - press enter"
                pygame.mixer.music.fadeout(2000)

        pygame.display.flip()

# Player 1 attack animation


# --- quit ---
pygame.display.quit()
pygame.quit()
sys.exit()

