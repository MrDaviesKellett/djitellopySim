import pygame
import threading
from random import uniform

SHOW_TRAILS = False
GRID = 0

class sim:

    def __init__(self):
        # Initialize Pygame
        pygame.init()

        # Set up the display
        self.width = 1000
        self.height = 1000
        self.running = True
        self.i = 0
        self.screen = pygame.display.set_mode((self.width, self.height))
        self.tellos = []
        self.image = pygame.image.load("tello.png")
        pygame.display.set_caption("Tello Simulation")
        self.update_thread = threading.Thread(target=self.update_visual)
        self.update_thread.start()

    def event_loop(self):
        # Handle events
        for _ in pygame.event.get():
            pass

    def register(self, tello):
        self.tellos.append(tello)
    
    def quit(self):
        self.running = False
        pygame.quit()

    def update_visual(self, windAmt=0.3):

        noise_x = 0
        noise_y = 0
        noise_z = 0
        noise_t = 0

        i = 0

        while self.running:
            noise_x = uniform(-windAmt, windAmt) + noise_x / 2
            noise_y = uniform(-windAmt, windAmt) + noise_y / 2
            noise_z = uniform(-windAmt, windAmt) + noise_z / 2
            noise_t = uniform(-windAmt, windAmt) + noise_t / 2

            self.screen.fill((0, 0, 0))
            if GRID:
                for x in range(0, self.width, GRID):
                    for y in range(0, self.height, GRID):
                        pygame.draw.rect(self.screen, (100, 100, 100), pygame.Rect(x, y, GRID, GRID), 1)

            for t in self.tellos:
                if t.is_flying and t.is_windy:
                        t.drone["pos"][0] += noise_x
                        t.drone["pos"][1] += noise_y
                        t.drone["pos"][2] += noise_z * 0.01
                        t.drone["rot"] += noise_t * 0.03

                        if t.drone["pos"][2] < 1:
                            t.drone["pos"][2] = 1

                t.flightPathTaken.append(tuple(t.drone["pos"]))

                if SHOW_TRAILS:
                    for path in t.flightPathTaken:
                        pygame.draw.rect(self.screen, (200, 200, 200), pygame.Rect(path[0], path[1], 2, 2))

                scaled_sprite = pygame.transform.scale(
                    self.image,
                    (
                        int(
                            t.drone["pos"][2]
                            * self.image.get_width()
                            * t.drone["scl"]
                        ),
                        int(
                            t.drone["pos"][2]
                            * self.image.get_height()
                            * t.drone["scl"]
                        ),
                    ),
                )
                if t.drone['flip'] > 0:
                    scaled_sprite = pygame.transform.scale(
                        scaled_sprite, (int(scaled_sprite.get_width()*abs(t.drone['flip'] - 12)/12), scaled_sprite.get_height())
                    )
                    t.drone['flip'] -= 1
                
                rotated_sprite = pygame.transform.rotate(
                    scaled_sprite, t.drone["rot"]
                )
                self.screen.blit(
                    rotated_sprite,
                    (
                        t.drone["pos"][0] - rotated_sprite.get_width() / 2,
                        t.drone["pos"][1] - rotated_sprite.get_height() / 2,
                    ),
                )
                pygame.draw.circle(self.screen, t.drone["led"], (
                        t.drone["pos"][0],
                        t.drone["pos"][1]
                    ), 10, 5)

            pygame.display.flip()
            pygame.time.delay(1000 // 60)

                


                    