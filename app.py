from __future__ import annotations

import sys

import pygame

from rescueroute.config import FPS, SCREEN_HEIGHT, SCREEN_WIDTH
from rescueroute.rendering import draw
from rescueroute.simulation import Simulation


def main() -> None:
    pygame.init()
    pygame.display.set_caption("RescueRoute AI - Smart Ambulance Dispatch")
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    clock = pygame.time.Clock()
    sim = Simulation(seed=11)

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    sim.spawn_emergency(force=True)
                elif event.key == pygame.K_t:
                    sim.randomize_traffic(show_message=True)
                elif event.key == pygame.K_b:
                    sim.toggle_random_block()
                elif event.key == pygame.K_c:
                    sim.reset_traffic_low()
                elif event.key == pygame.K_s:
                    sim.export_demo_data()
                    sim.add_message("Dashboard CSV files saved.")

        sim.update(dt)
        draw(sim, screen)
        pygame.display.flip()

    sim.export_demo_data()
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
