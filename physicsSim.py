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
        flip_frames = tello.drone.get("flip", 0)
        flip_direction = tello.drone.get("flip_direction", "b")
        flip_angle = ((24 - flip_frames) / 24) * math.tau if flip_frames > 0 else 0

        def point(local):
            x, y = local[0], local[1]
            z = 0
            if flip_frames > 0:
                direction = -1 if flip_direction in {"b", "r"} else 1
                if flip_direction in {"f", "b"}:
                    y, z = y * math.cos(flip_angle), direction * y * math.sin(flip_angle)
                else:
                    x, z = x * math.cos(flip_angle), direction * x * math.sin(flip_angle)
            rx, ry, rz = self._rotate_point(x, y, z / 100, yaw, 0, 0)
            return self._world_to_screen(pos[0] + rx, pos[1] + ry, pos[2] + rz)

        return point

    def _draw_rotor(self, center, radius):
        pygame.draw.circle(self.screen, (31, 41, 48), center, radius)
        pygame.draw.circle(self.screen, (94, 109, 121), center, radius, 2)
        pygame.draw.line(self.screen, (177, 186, 194), (center[0] - radius, center[1]), (center[0] + radius, center[1]), 2)
        pygame.draw.line(self.screen, (177, 186, 194), (center[0], center[1] - radius), (center[0], center[1] + radius), 2)

    def _mled_color(self, value):
        value = value.lower()
        if value == "r":
            return (245, 42, 60)
        if value == "b":
            return (54, 110, 255)
        if value in {"p", "m"}:
            return (190, 38, 255)
        return (17, 20, 24)

    def _draw_expansion_kit(self, tello, body_center, body_width, body_height):
        led = tello.drone.get("led", (0, 0, 0))
        led_center = (int(body_center[0]), int(body_center[1] - body_height / 2 - 7))
        pygame.draw.circle(self.screen, (12, 14, 16), led_center, 7)
        if any(led):
            pygame.draw.circle(self.screen, led, led_center, 5)
        else:
            pygame.draw.circle(self.screen, (46, 52, 58), led_center, 5, 1)

        pattern = tello.drone.get("mled", "")
        if not pattern:
            return

        cell = 4
        gap = 1
        panel_size = 8 * cell + 7 * gap
        panel = pygame.Rect(0, 0, panel_size + 6, panel_size + 6)
        panel.center = (int(body_center[0]), int(body_center[1] + body_height / 2 + panel.height / 2 + 4))
        pygame.draw.rect(self.screen, (8, 10, 12), panel, border_radius=2)
        pygame.draw.rect(self.screen, (81, 92, 102), panel, 1, border_radius=2)

        start_x = panel.x + 3
        start_y = panel.y + 3
        for row in range(8):
            for col in range(8):
                index = row * 8 + col
                color = self._mled_color(pattern[index] if index < len(pattern) else "0")
                rect = pygame.Rect(start_x + col * (cell + gap), start_y + row * (cell + gap), cell, cell)
                pygame.draw.rect(self.screen, color, rect)

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

        flip_phase = tello.drone.get("flip", 0)
        flip_direction = tello.drone.get("flip_direction", "b")
        flip_angle = ((24 - flip_phase) / 24) * math.tau if flip_phase > 0 else 0
        body_width = 58
        body_height = 38
        if flip_phase > 0 and flip_direction in {"l", "r"}:
            body_width = max(10, int(body_width * abs(math.cos(flip_angle))))
        elif flip_phase > 0:
            body_height = max(8, int(body_height * abs(math.cos(flip_angle))))

        body_rect = pygame.Rect(0, 0, body_width, body_height)
        body_rect.center = (int(body_center[0]), int(body_center[1]))
        pygame.draw.ellipse(self.screen, (53, 67, 77), body_rect)
        pygame.draw.ellipse(self.screen, (211, 218, 224), body_rect, 2)
        self._draw_expansion_kit(tello, body_center, body_width, body_height)

        for rotor in rotors:
            self._draw_rotor((int(rotor[0]), int(rotor[1])), 17)

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

            self._draw_drone_3d(tello)

            if tello.drone.get("flip", 0) > 0:
                tello.drone["flip"] -= 1

        pygame.display.flip()

    def update_visual(self, windAmt=0.3):
        while self.running:
            self.render_frame(windAmt=windAmt)
            time.sleep(1 / 60)
