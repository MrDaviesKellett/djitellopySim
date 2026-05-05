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
        self._main_thread_id = threading.get_ident()
        self._lock = threading.RLock()
        self._noise_x = 0
        self._noise_y = 0
        self._noise_z = 0
        self._noise_t = 0
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Tello Simulation - 3D")
        self.render_frame(apply_wind=False)

    def event_loop(self):
        if not self._can_use_pygame():
            return
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
        if self._can_use_pygame():
            pygame.quit()

    def _can_use_pygame(self):
        return self.running and threading.get_ident() == self._main_thread_id

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

        def point(local):
            rx, ry, rz = self._rotate_point(local[0], local[1], 0, yaw, 0, 0)
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
        body_center = point((0, 0, 0))

        rotors = [
            point((-72, 54, 0)),
            point((72, 54, 0)),
            point((-72, -54, 0)),
            point((72, -54, 0)),
        ]

        arm_color = (118, 132, 143)
        pygame.draw.line(self.screen, arm_color, rotors[0], rotors[3], 7)
        pygame.draw.line(self.screen, arm_color, rotors[1], rotors[2], 7)

        body_rect = pygame.Rect(0, 0, 58, 38)
        body_rect.center = (int(body_center[0]), int(body_center[1]))
        pygame.draw.ellipse(self.screen, (53, 67, 77), body_rect)
        pygame.draw.ellipse(self.screen, (211, 218, 224), body_rect, 2)

        flip_phase = tello.drone.get("flip", 0)
        rotor_radius = 17 if flip_phase == 0 else max(6, int(17 * abs(flip_phase - 12) / 12))
        for index, rotor in enumerate(rotors):
            self._draw_rotor((int(rotor[0]), int(rotor[1])), rotor_radius, tello.drone.get("led") if index == 0 else None)

        top = self._world_to_screen(pos[0], pos[1], pos[2])
        ground = self._world_to_screen(pos[0], pos[1], 0)
        pygame.draw.line(self.screen, ALTITUDE_COLOR, (top[0] - 40, top[1]), (ground[0] - 40, ground[1]), 2)
        height_cm = int(max(0, (pos[2] - 1.0) * 100))
        font = pygame.font.Font(None, 22)
        label = font.render(f"{height_cm} cm", True, ALTITUDE_COLOR)
        self.screen.blit(label, (top[0] - 30, top[1] - 24))

    def render_frame(self, windAmt=0.3, apply_wind=True):
        if not self._can_use_pygame():
            return

        self.event_loop()
        if not self.running:
            return

        if apply_wind:
            self._noise_x = uniform(-windAmt, windAmt) + self._noise_x / 2
            self._noise_y = uniform(-windAmt, windAmt) + self._noise_y / 2
            self._noise_z = uniform(-windAmt, windAmt) + self._noise_z / 2
            self._noise_t = uniform(-windAmt, windAmt) + self._noise_t / 2
        else:
            self._noise_x = self._noise_y = self._noise_z = self._noise_t = 0

        self.screen.fill(BACKGROUND)
        self._draw_grid()

        with self._lock:
            tellos = list(self.tellos)

        for tello in tellos:
            if apply_wind and tello.is_flying and tello.is_windy:
                tello.drone["pos"][0] += self._noise_x
                tello.drone["pos"][1] += self._noise_y
                tello.drone["pos"][2] = max(1.0, tello.drone["pos"][2] + self._noise_z * 0.01)
                tello.drone["rot"] += self._noise_t * 0.03

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

    def update_visual(self, windAmt=0.3):
        while self.running:
            self.render_frame(windAmt=windAmt)
            time.sleep(1 / 60)
