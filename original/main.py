import asyncio
import random
import pygame

pygame.init()
W, H = 800, 600
screen = pygame.display.set_mode((W, H))
pygame.display.set_caption("Asteroid War")
clock = pygame.time.Clock()
font = pygame.font.Font(None, 32)

async def main():
    ship = pygame.Rect(375, 530, 50, 50)
    shots, enemies = [], []
    score, lives = 0, 3
    spawn, cooldown = 0, 0
    while True:
        dt = min(clock.tick(60) / 1000, .05)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return
            if event.type == pygame.KEYDOWN and event.key == pygame.K_r and lives <= 0:
                score, lives = 0, 3
                shots.clear()
                enemies.clear()
                ship.topleft = (375, 530)
                spawn = cooldown = 0
        if lives > 0:
            keys = pygame.key.get_pressed()
            ship.x += round(400 * dt * (int(keys[pygame.K_RIGHT] or keys[pygame.K_d]) - int(keys[pygame.K_LEFT] or keys[pygame.K_a])))
            ship.y += round(400 * dt * (int(keys[pygame.K_DOWN] or keys[pygame.K_s]) - int(keys[pygame.K_UP] or keys[pygame.K_w])))
            ship.clamp_ip(screen.get_rect())
            cooldown -= dt
            if keys[pygame.K_SPACE] and cooldown <= 0:
                shots.append(pygame.Rect(ship.centerx-3, ship.top, 6, 15))
                cooldown = .25
            spawn += dt
            if spawn >= 1:
                spawn = 0
                enemies.append(pygame.Rect(random.randrange(W-40), -40, 40, 40))
            for shot in shots[:]:
                shot.y -= round(500 * dt)
                if shot.bottom < 0:
                    shots.remove(shot)
            for enemy in enemies[:]:
                enemy.y += round(130 * dt)
                if enemy.colliderect(ship) or enemy.top > H:
                    enemies.remove(enemy)
                    lives -= 1
                    if lives <= 0:
                        break
                    continue
                hit = next((s for s in shots if s.colliderect(enemy)), None)
                if hit is not None:
                    shots.remove(hit)
                    enemies.remove(enemy)
                    score += 10
        screen.fill((5, 8, 20))
        pygame.draw.polygon(screen, (50, 230, 130), [ship.midtop, ship.bottomleft, ship.bottomright])
        for enemy in enemies:
            pygame.draw.rect(screen, (240, 60, 60), enemy)
        for shot in shots:
            pygame.draw.rect(screen, (255, 220, 60), shot)
        screen.blit(font.render(f"Pontos: {score}   Vidas: {lives}", True, "white"), (15, 15))
        if lives <= 0:
            text = font.render("Fim de jogo - R para reiniciar", True, "white")
            screen.blit(text, text.get_rect(center=(W//2,H//2)))
        pygame.display.flip()
        await asyncio.sleep(0)

asyncio.run(main())
