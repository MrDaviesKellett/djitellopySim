import math
import threading
import time
from random import uniform

import pygame

SHOW_TRAILS = False
GRID = 100
BACKGROUND = (14, 18, 22)
GRID_COLOR = (38, 46, 54)
FLOOR_COLOR = (25, 31, 36)
ALTITUDE_COLOR = (94, 234, 212)


class sim:
    def __init__(self, width=1000, height=800):
        pygame.init()
        self.width = width
        self.height = height
        self.running = True
        self.tellos = []
        self._lock = threading.RLock()
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Tello Simulation - 3D")
        self.update_thread = threading.Thread(target=self.update_visual, daemon=True)
        self.update_thread.start()

    def event_loop(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.quit()

    def register(self, tello):
        with self._lock:
            if tello not in self.tellos:
                self.tellos.append(tello)

    def unregister(self, tello):
        with self._lock:
            if tello in self.tellos:
                self.tellos.remove(tello)

    def quit(self):
        self.running = False
        pygame.quit()

    def _world_to_screen(self, x, y, z):
        sx = self.width / 2 + (x - self.width / 2) * 0.72 - (y - self.height / 2) * 0.28
        sy = self.height * 0.74 + (x - self.width / 2) * 0.18 + (y - self.height / 2) * 0.42 - z * 112
        return sx, sy

    def _rotate_point(self, x, y, z, yaw, pitch, roll):
        cy, sy = math.cos(yaw), math.sin(yaw)
        cp, sp = math.cos(pitch), math.sin(pitch)
        cr, sr = math.cos(roll), math.sin(roll)

        x, y = x * cy - y * sy, x * sy + y * cy
        y, z = y * cp - z * sp, y * sp + z * cp
        x, z = x * cr + z * sr, -x * sr + z * cr
        return x, y, z

    def _draw_grid(self):
        horizon = int(self.height * 0.2)
        pygame.draw.rect(self.screen, FLOOR_COLOR, pygame.Rect(0, horizon, self.width, self.height - horizon))
        if not GRID:
            return
        for value in range(-800, 1800, GRID):
            start = self._world_to_screen(value, -600, 0)
            end = self._world_to_screen(value, 1600, 0)
            pygame.draw.line(self.screen, GRID_COLOR, start, end, 1)
            start = self._world_to_screen(-800, value, 0)
            end = self._world_to_screen(1800, value, 0)
            pygame.draw.line(self.screen, GRID_COLOR, start, end, 1)

    def _project_drone_points(self, tello):
        pos = tello.drone["pos"]
        yaw = math.radians(tello.drone["rot"])
        pitch = math.radians(tello.drone.get("pitch", 0))
        roll = math.radians(tello.drone.get("roll", 0))

        def point(local):
            rx, ry, rz = self._rotate_point(*local, yaw, pitch, roll)
            return self._world_to_screen(pos[0] + rx, pos[1] + ry, pos[2] + rz)

        return point

    def _draw_rotor(self, center, radius, led=None):
        pygame.draw.circle(self.screen, (31, 41, 48), center, radius)
        pygame.draw.circle(self.screen, (94, 109, 121), center, radius, 2)
        pygame.draw.line(self.screen, (177, 186, 194), (center[0] - radius, center[1]), (center[0] + radius, center[1]), 2)
        pygame.draw.line(self.screen, (177, 186, 194), (center[0], center[1] - radius), (center[0], center[1] + radius), 2)
        if led is not None and any(led):
            pygame.draw.circle(self.screen, led, center, max(4, radius // 3))

    def _draw_drone_3d(self, tello):
        pos = tello.drone["pos"]
        shadow = self._world_to_screen(pos[0], pos[1], 0)
        altitude = max(0.0, pos[2])
        shadow_radius = max(16, int(44 / (1 + altitude * 0.15)))
        pygame.draw.ellipse(
            self.screen,
            (4, 7, 10),
            pygame.Rect(shadow[0] - shadow_radius * 1.4, shadow[1] - shadow_radius * 0.45, shadow_radius * 2.8, shadow_radius * 0.9),
        )

        point = self._project_drone_points(tello)
        body_front = point((0, 28, 0))
        body_back = point((0, -30, 0))
        body_left = point((-34, 0, 0))
        body_right = point((34, 0, 0))
        body_top = point((0, 0, 15))
        body_bottom = point((0, 0, -8))

        rotors = [
            point((-72, 54, 0)),
            point((72, 54, 0)),
            point((-72, -54, 0)),
            point((72, -54, 0)),
        ]

        for rotor in rotors:
            pygame.draw.line(self.screen, (112, 126, 140), body_top, rotor, 6)
            pygame.draw.line(self.screen, (27, 36, 43), body_bottom, rotor, 3)

        body_poly = [body_front, body_right, body_back, body_left]
        pygame.draw.polygon(self.screen, (52, 69, 80), body_poly)
        pygame.draw.polygon(self.screen, (157, 168, 176), [body_top, body_right, body_front])
        pygame.draw.polygon(self.screen, (92, 107, 118), [body_top, body_left, body_back, body_right])
        pygame.draw.polygon(self.screen, (221, 226, 230), body_poly, 2)

        flip_phase = tello.drone.get("flip", 0)
        rotor_radius = 17 if flip_phase == 0 else max(6, int(17 * abs(flip_phase - 12) / 12))
        for index, rotor in enumerate(rotors):
            self._draw_rotor((int(rotor[0]), int(rotor[1])), rotor_radius, tello.drone.get("led") if index == 0 else None)

        top = self._world_to_screen(pos[0], pos[1], pos[2])
        ground = self._world_to_screen(pos[0], pos[1], 0)
        pygame.draw.line(self.screen, ALTITUDE_COLOR, top, ground, 2)
        height_cm = int(max(0, (pos[2] - 1.0) * 100))
        font = pygame.font.Font(None, 22)
        label = font.render(f"{height_cm} cm", True, ALTITUDE_COLOR)
        self.screen.blit(label, (top[0] + 12, top[1] - 10))

    def update_visual(self, windAmt=0.3):
        noise_x = noise_y = noise_z = noise_t = 0
        while self.running:
            self.event_loop()
            noise_x = uniform(-windAmt, windAmt) + noise_x / 2
            noise_y = uniform(-windAmt, windAmt) + noise_y / 2
            noise_z = uniform(-windAmt, windAmt) + noise_z / 2
            noise_t = uniform(-windAmt, windAmt) + noise_t / 2

            self.screen.fill(BACKGROUND)
            self._draw_grid()

            with self._lock:
                tellos = list(self.tellos)

            for tello in tellos:
                if tello.is_flying and tello.is_windy:
                    tello.drone["pos"][0] += noise_x
                    tello.drone["pos"][1] += noise_y
                    tello.drone["pos"][2] = max(1.0, tello.drone["pos"][2] + noise_z * 0.01)
                    tello.drone["rot"] += noise_t * 0.03

                tello.flightPathTaken.append(tuple(tello.drone["pos"]))
                if len(tello.flightPathTaken) > 2000:
                    tello.flightPathTaken = tello.flightPathTaken[-1000:]

                if SHOW_TRAILS:
                    for path in tello.flightPathTaken:
                        pygame.draw.circle(self.screen, (130, 140, 148), self._world_to_screen(path[0], path[1], 0), 2)

                if tello.drone.get("flip", 0) > 0:
                    tello.drone["flip"] -= 1

                self._draw_drone_3d(tello)

            pygame.display.flip()
            time.sleep(1 / 60)
