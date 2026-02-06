def draw_arrow(screen, rect, direction, color):
    dx, dy = direction
    size = 12

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


def main_menu(screen, clock):
    font_title = pygame.font.SysFont(None, 96)
    font_hint = pygame.font.SysFont(None, 36)

    title = font_title.render("PYGAME FIGHTING", True, (255, 255, 255))
    hint = font_hint.render("Press ENTER to Start", True, (200, 200, 200))

    while True:
        clock.tick(60)
        screen.fill((20, 20, 20))

        # draw text
        screen.blit(
            title,
            title.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 60))
        )
        screen.blit(
            hint,
            hint.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 40))
        )

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    return "start"

                if event.key == pygame.K_ESCAPE:
                    return "quit"

        pygame.display.flip()


ATTACKS = {
    "normal": {
        "dmg": 10,
        "size": 40,
        "frames": 10,
        "cooldown": 30,
    },
    "super": {
        "dmg": 25,
        "size": 1000,
        "frames": 18,
        "cooldown": 90,
    },
    "dash": {
        "dmg": 15,
        "size": 50,
        "frames": 15,
        "cooldown": 60,
        "speed": 25,
    },
}

P1_COLORS = {
    "normal": (255, 200, 50),
    "super": (255, 100, 0),
    "dash": (255, 200, 200)
}

P2_COLORS = {
    "normal": (50, 200, 255),
    "super": (0, 150, 255),
    "dash": (200, 200, 255)
}

import pygame
import sys

# --- setup ---
pygame.init()

WIDTH, HEIGHT = 1000, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Pygame fighting")

clock = pygame.time.Clock()

# --- player ---
font = pygame.font.SysFont(None, 80)
p1_dir = (1, 0)  # (x, y)
p2_dir = (-1, 0)

countdown = 120
win = False
running = True
winner_text = ""
player_size = 40
maxhp = 100
player_x = 10
player_y = 10
player2_x = 800
player2_y = 400
speed = 5
p1hp = maxhp
p2hp = maxhp
p1_attack = None
p1_cd = 0
p1_anim = 0
p1_hit = False

p2_attack = None
p2_cd = 0
p2_anim = 0
p2_hit = False

menu_result = main_menu(screen, clock)
if menu_result == "quit":
    running = False
# --- game loop ---
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
    if not win:
        clock.tick(60)  # 60 FPS

        # --- events ---

        keys = pygame.key.get_pressed()

        # --- input ---
        # Player 1
        if keys[pygame.K_a]:
            player_x -= speed
            p1_dir = (-1, 0)
        if keys[pygame.K_d]:
            player_x += speed
            p1_dir = (1, 0)
        if keys[pygame.K_w]:
            player_y -= speed
            p1_dir = (0, -1)
        if keys[pygame.K_s]:
            player_y += speed
            p1_dir = (0, 1)

        # Player 2
        if keys[pygame.K_LEFT]:
            player2_x -= speed
            p2_dir = (-1, 0)
        if keys[pygame.K_RIGHT]:
            player2_x += speed
            p2_dir = (1, 0)
        if keys[pygame.K_UP]:
            player2_y -= speed
            p2_dir = (0, -1)
        if keys[pygame.K_DOWN]:
            player2_y += speed
            p2_dir = (0, 1)

        # Player 1 attacks
        if p1_cd == 0:
            if keys[pygame.K_r]:
                p1_attack = "super"
                p1_anim = ATTACKS["super"]["frames"]
                p1_cd = ATTACKS["super"]["cooldown"]
                p1_hit = False
            elif keys[pygame.K_q]:
                p1_attack = "dash"
                p1_anim = ATTACKS["dash"]["frames"]
                p1_cd = ATTACKS["dash"]["cooldown"]
                p1_hit = False
            elif keys[pygame.K_e]:
                p1_attack = "normal"
                p1_anim = ATTACKS["normal"]["frames"]
                p1_cd = ATTACKS["normal"]["cooldown"]
                p1_hit = False

        # Player 2 attacks
        if p2_cd == 0:
            if keys[pygame.K_PERIOD]:
                p2_attack = "super"
                p2_anim = ATTACKS["super"]["frames"]
                p2_cd = ATTACKS["super"]["cooldown"]
                p2_hit = False
            elif keys[pygame.K_RSHIFT]:
                p2_attack = "dash"
                p2_anim = ATTACKS["dash"]["frames"]
                p2_cd = ATTACKS["dash"]["cooldown"]
                p2_hit = False
            elif keys[pygame.K_SLASH]:
                p2_attack = "normal"
                p2_anim = ATTACKS["normal"]["frames"]
                p2_cd = ATTACKS["normal"]["cooldown"]
                p2_hit = False
        if p1_cd > 0:
            p1_cd -= 1
        if p1_anim > 0:
            p1_anim -= 1
            if p1_anim == 0:
                p1_attack = None

        if p2_cd > 0:
            p2_cd -= 1
        if p2_anim > 0:
            p2_anim -= 1
            if p2_anim == 0:
                p2_attack = None
        # Player 1 dash movement
        if p1_attack == "dash" and p1_anim > 0:
            dx, dy = p1_dir
            player_x += dx * ATTACKS["dash"]["speed"]
            player_y += dy * ATTACKS["dash"]["speed"]

        # Player 2 dash movement
        if p2_attack == "dash" and p2_anim > 0:
            dx, dy = p2_dir
            player2_x += dx * ATTACKS["dash"]["speed"]
            player2_y += dy * ATTACKS["dash"]["speed"]

        player_x = max(0, min(player_x, WIDTH - player_size))
        player_y = max(0, min(player_y, HEIGHT - player_size))

        player2_x = max(0, min(player2_x, WIDTH - player_size))
        player2_y = max(0, min(player2_y, HEIGHT - player_size))

        # --- draw ---
        screen.fill((30, 30, 30))  # background
        p1_rect = pygame.Rect(player_x, player_y, player_size, player_size)
        p2_rect = pygame.Rect(player2_x, player2_y, player_size, player_size)

        pygame.draw.rect(screen, (200, 50, 50), p1_rect)
        pygame.draw.rect(screen, (50, 50, 200), p2_rect)
        draw_arrow(screen, p1_rect, p1_dir, (50, 50, 50))
        draw_arrow(screen, p2_rect, p2_dir, (50, 50, 50))

        hitbox1 = None
        hitbox2 = None

        if p1_attack:
            atk = ATTACKS[p1_attack]
            dx, dy = p1_dir

            if dx == 1:  # right
                hitbox1 = pygame.Rect(
                    player_x + player_size,
                    player_y,
                    atk["size"],
                    player_size
                )

            elif dx == -1:  # left
                hitbox1 = pygame.Rect(
                    player_x - atk["size"],
                    player_y,
                    atk["size"],
                    player_size
                )

            elif dy == 1:  # down
                hitbox1 = pygame.Rect(
                    player_x,
                    player_y + player_size,
                    player_size,
                    atk["size"]
                )

            elif dy == -1:  # up
                hitbox1 = pygame.Rect(
                    player_x,
                    player_y - atk["size"],
                    player_size,
                    atk["size"]
                )

            pygame.draw.rect(screen, P1_COLORS[p1_attack], hitbox1)

        if p2_attack:
            atk = ATTACKS[p2_attack]
            dx, dy = p2_dir

            if dx == 1:  # right
                hitbox2 = pygame.Rect(
                    player2_x + player_size,
                    player2_y,
                    atk["size"],
                    player_size
                )

            elif dx == -1:  # left
                hitbox2 = pygame.Rect(
                    player2_x - atk["size"],
                    player2_y,
                    atk["size"],
                    player_size
                )

            elif dy == 1:  # down
                hitbox2 = pygame.Rect(
                    player2_x,
                    player2_y + player_size,
                    player_size,
                    atk["size"]
                )

            elif dy == -1:  # up
                hitbox2 = pygame.Rect(
                    player2_x,
                    player2_y - atk["size"],
                    player_size,
                    atk["size"]
                )

            pygame.draw.rect(screen, P2_COLORS[p2_attack], hitbox2)

        if hitbox1 and hitbox1.colliderect(p2_rect) and not p1_hit:
            p2hp -= ATTACKS[p1_attack]["dmg"]
            p1_hit = True

        if hitbox2 and hitbox2.colliderect(p1_rect) and not p2_hit:
            p1hp -= ATTACKS[p2_attack]["dmg"]
            p2_hit = True

        p1hp = max(0, p1hp)
        p2hp = max(0, p2hp)
    if win:
        countdown -= 1
        if countdown <= 0:
            running = False
        overlay = pygame.Surface((WIDTH, HEIGHT))
        overlay.set_alpha(160)
        overlay.fill((0, 0, 0))
        screen.blit(overlay, (0, 0))

        text_surface = font.render(winner_text, True, (255, 255, 255))
        text_rect = text_surface.get_rect(center=(WIDTH // 2, HEIGHT // 2))
        screen.blit(text_surface, text_rect)

    BAR_WIDTH = 300
    BAR_HEIGHT = 20

    # Player 1 HP bar
    pygame.draw.rect(screen, (100, 100, 100), (50, 30, BAR_WIDTH, BAR_HEIGHT))
    pygame.draw.rect(
        screen,
        (50, 255, 50),
        (50, 30, BAR_WIDTH * (p1hp / maxhp), BAR_HEIGHT)
    )

    # Player 2 HP bar
    pygame.draw.rect(screen, (100, 100, 100), (WIDTH - 350, 30, BAR_WIDTH, BAR_HEIGHT))
    pygame.draw.rect(
        screen,
        (50, 255, 50),
        (WIDTH - 350, 30, BAR_WIDTH * (p2hp / maxhp), BAR_HEIGHT)
    )
    if not win:
        if p1hp <= 0:
            win = True
            winner_text = "PLAYER 2 WINS"
        elif p2hp <= 0:
            win = True
            winner_text = "PLAYER 1 WINS"

    pygame.display.flip()

# Player 1 attack animation


# --- quit ---
pygame.display.quit()
pygame.quit()
sys.exit()

