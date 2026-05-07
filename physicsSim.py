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
GATE_PENDING = (251, 191, 36)
GATE_ACTIVE = (56, 189, 248)
GATE_PASSED = (74, 222, 128)
GATE_SHADOW = (5, 8, 12)


class sim:
    def __init__(self, width=1000, height=800):
        """Create and initialise this object."""
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
        self.camera_mode = "follow"
        self.camera_x = self.width / 2
        self.camera_y = self.height / 2
        self.camera_z = 0.0
        self.camera_zoom = 1.0
        self.show_keymap = True
        self.summary_buttons = []
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Tello Simulation - 3D")
        self.render_frame(apply_wind=False)

    def event_loop(self):
        """Handle pygame window, mouse, and keyboard events."""
        if not self._can_use_pygame():
            return
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.quit()
            elif event.type == pygame.KEYDOWN:
                self._handle_keydown(event.key)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._handle_mouse_down(event.pos)

    def _handle_keydown(self, key):
        if key == pygame.K_f:
            self.set_camera_follow(True)
        elif key == pygame.K_o:
            self.set_camera_overview()
        elif key in {pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS}:
            self.camera_zoom = min(2.5, self.camera_zoom * 1.15)
        elif key in {pygame.K_MINUS, pygame.K_KP_MINUS}:
            self.camera_zoom = max(0.12, self.camera_zoom / 1.15)
        elif key == pygame.K_k:
            self.show_keymap = not self.show_keymap
        elif self.tellos and key == pygame.K_v:
            hints = self.tellos[0].drone.get("race_hints", {})
            hints["forward"] = not hints.get("forward", False)
        elif self.tellos and key in {pygame.K_d, pygame.K_h, pygame.K_r}:
            hints = self.tellos[0].drone.get("race_hints", {})
            if key == pygame.K_d:
                hints["distance"] = not hints.get("distance", False)
            elif key == pygame.K_h:
                hints["height"] = not hints.get("height", False)
            elif key == pygame.K_r:
                hints["relative"] = not hints.get("relative", False)

    def _handle_mouse_down(self, pos):
        for rect, action, tello in self.summary_buttons:
            if rect.collidepoint(pos):
                if action == "close":
                    self.quit()
                elif action == "again":
                    tello._reset_race_timer()
                    tello.drone["race_next_gate"] = 0
                    tello.drone["race_completed"] = False
                    tello.drone["race_last_pos"] = list(tello.drone["pos"])
                break

    def register(self, tello):
        """Register a drone with the simulator renderer."""
        with self._lock:
            if tello not in self.tellos:
                self.tellos.append(tello)

    def unregister(self, tello):
        """Remove a drone from the simulator renderer."""
        with self._lock:
            if tello in self.tellos:
                self.tellos.remove(tello)

    def quit(self):
        """Close the simulator window and stop rendering."""
        self.running = False
        if self._can_use_pygame():
            pygame.quit()

    def _can_use_pygame(self):
        return self.running and threading.get_ident() == self._main_thread_id

    def set_camera_follow(self, enabled=True):
        """Use set_camera_follow in the simulator API."""
        self.camera_mode = "follow" if enabled else "static"
        if enabled:
            self.camera_zoom = 1.0

    def set_camera_overview(self):
        """Use set_camera_overview in the simulator API."""
        self.camera_mode = "overview"

    def _world_to_screen(self, x, y, z):
        sx = self.width / 2 + ((x - self.camera_x) * 0.72 - (y - self.camera_y) * 0.28) * self.camera_zoom
        sy = self.height * 0.68 + ((x - self.camera_x) * 0.18 + (y - self.camera_y) * 0.42 - (z - self.camera_z) * 112) * self.camera_zoom
        return sx, sy

    def _update_camera(self, tellos):
        if not tellos:
            return
        lead = tellos[0]
        if self.camera_mode == "follow":
            self.camera_x += (lead.drone["pos"][0] - self.camera_x) * 0.18
            self.camera_y += (lead.drone["pos"][1] - self.camera_y) * 0.18
            self.camera_z += (lead.drone["pos"][2] - self.camera_z) * 0.18
        elif self.camera_mode == "overview":
            self.camera_z = 0.0
            points = [lead.drone["pos"]]
            for tello in tellos:
                for gate in tello.drone.get("race_gates", []):
                    x, y, _ = gate["pos"]
                    radius = gate.get("radius", 190)
                    points.extend([[x - radius, y], [x + radius, y], [x, y - radius], [x, y + radius]])
            min_x = min(point[0] for point in points)
            max_x = max(point[0] for point in points)
            min_y = min(point[1] for point in points)
            max_y = max(point[1] for point in points)
            self.camera_x = (min_x + max_x) / 2
            self.camera_y = (min_y + max_y) / 2

            projected = []
            old_zoom = self.camera_zoom
            self.camera_zoom = 1.0
            for point in points:
                projected.append(self._world_to_screen(point[0], point[1], 0))
            self.camera_zoom = old_zoom
            span_x = max(px for px, _ in projected) - min(px for px, _ in projected)
            span_y = max(py for _, py in projected) - min(py for _, py in projected)
            target_zoom = min((self.width * 0.78) / max(span_x, 1), (self.height * 0.72) / max(span_y, 1), 1.0)
            self.camera_zoom += (max(0.12, target_zoom) - self.camera_zoom) * 0.25

    def _rotate_point(self, x, y, z, yaw, pitch, roll):
        cy, sy = math.cos(yaw), math.sin(yaw)
        cp, sp = math.cos(pitch), math.sin(pitch)
        cr, sr = math.cos(roll), math.sin(roll)

        x, y = x * cy - y * sy, x * sy + y * cy
        y, z = y * cp - z * sp, y * sp + z * cp
        x, z = x * cr + z * sr, -x * sr + z * cr
        return x, y, z

    def _draw_grid(self):
        horizon = 0
        pygame.draw.rect(self.screen, FLOOR_COLOR, pygame.Rect(0, horizon, self.width, self.height - horizon))
        if not GRID:
            return
        grid_x = int(self.camera_x // GRID) * GRID
        grid_y = int(self.camera_y // GRID) * GRID
        for value in range(grid_x - 1800, grid_x + 1900, GRID):
            start = self._world_to_screen(value, grid_y - 1800, 0)
            end = self._world_to_screen(value, grid_y + 1900, 0)
            pygame.draw.line(self.screen, GRID_COLOR, start, end, 1)
        for value in range(grid_y - 1800, grid_y + 1900, GRID):
            start = self._world_to_screen(grid_x - 1800, value, 0)
            end = self._world_to_screen(grid_x + 1900, value, 0)
            pygame.draw.line(self.screen, GRID_COLOR, start, end, 1)

    def _draw_race_curve(self, tello):
        curve = tello.drone.get("race_curve", [])
        if len(curve) < 2:
            return
        points = [(int(x), int(y)) for x, y in (self._world_to_screen(point[0], point[1], max(point[2], 1.0)) for point in curve)]
        pygame.draw.lines(self.screen, (76, 91, 108), False, points, 2)

    def _draw_polyline_segments(self, points, color, width):
        segment = []
        for point in points:
            if point is None:
                if len(segment) > 1:
                    pygame.draw.lines(self.screen, color, False, [(int(px), int(py)) for px, py in segment], width)
                segment = []
            else:
                segment.append(point)
        if len(segment) > 1:
            pygame.draw.lines(self.screen, color, False, [(int(px), int(py)) for px, py in segment], width)

    def _draw_race_gate(self, tello, gate, active=False, layer="full"):
        x, y, z = gate["pos"]
        yaw = math.radians(gate["yaw"])
        side_x = math.cos(yaw)
        side_y = -math.sin(yaw)
        radius = gate.get("radius", 320)
        color = GATE_PASSED if gate.get("passed") else GATE_ACTIVE if active else GATE_PENDING
        width = 6 if active else 4

        if layer == "shadow":
            if gate.get("type") == "arch":
                base_l = self._world_to_screen(x - side_x * radius, y - side_y * radius, 0)
                base_r = self._world_to_screen(x + side_x * radius, y + side_y * radius, 0)
            else:
                base_l = self._world_to_screen(x - side_x * radius, y - side_y * radius, 0)
                base_r = self._world_to_screen(x + side_x * radius, y + side_y * radius, 0)
            pygame.draw.line(self.screen, GATE_SHADOW, (int(base_l[0]), int(base_l[1])), (int(base_r[0]), int(base_r[1])), 8)
            return

        if gate.get("type") == "arch":
            angles = [math.pi * step / 24 for step in range(25)]
            points = [
                self._world_to_screen(
                    x + side_x * math.cos(angle) * radius,
                    y + side_y * math.cos(angle) * radius,
                    z + math.sin(angle) * radius / 100,
                )
                for angle in angles
            ]
            base_l = self._world_to_screen(x - side_x * radius, y - side_y * radius, z)
            base_r = self._world_to_screen(x + side_x * radius, y + side_y * radius, z)
            if layer == "lower":
                pygame.draw.line(self.screen, (128, 138, 148), (int(base_l[0]), int(base_l[1])), (int(base_l[0]), int(base_l[1] - 8)), width)
                pygame.draw.line(self.screen, (128, 138, 148), (int(base_r[0]), int(base_r[1])), (int(base_r[0]), int(base_r[1] - 8)), width)
                return
            pygame.draw.lines(self.screen, color, False, [(int(px), int(py)) for px, py in points], width)
            pygame.draw.line(self.screen, color, (int(base_l[0]), int(base_l[1])), (int(base_l[0]), int(base_l[1] - 8)), width)
            pygame.draw.line(self.screen, color, (int(base_r[0]), int(base_r[1])), (int(base_r[0]), int(base_r[1] - 8)), width)
            label_anchor = points[12]
        else:
            angles = [math.tau * step / 48 for step in range(49)]
            lower_points = []
            upper_points = []
            last_lower = False
            last_upper = False
            all_points = []
            all_sines = []
            for angle in angles:
                screen_point = self._world_to_screen(
                    x + side_x * math.cos(angle) * radius,
                    y + side_y * math.cos(angle) * radius,
                    z + math.sin(angle) * radius / 100,
                )
                all_points.append(screen_point)
                all_sines.append(math.sin(angle))
                is_upper = math.sin(angle) >= 0
                if is_upper:
                    if last_lower:
                        lower_points.append(screen_point)
                    upper_points.append(screen_point)
                else:
                    if last_upper:
                        upper_points.append(screen_point)
                    lower_points.append(screen_point)
                if len(all_points) > 1:
                    if is_upper != last_upper:
                        lower_points.append(None)
                        upper_points.append(None)
                last_lower = not is_upper
                last_upper = is_upper
            points = [
                self._world_to_screen(
                    x + side_x * math.cos(angle) * radius,
                    y + side_y * math.cos(angle) * radius,
                    z + math.sin(angle) * radius / 100,
                )
                for angle in angles
            ]
            pole_top = self._world_to_screen(x, y, z - radius / 100)
            pole_base = self._world_to_screen(x, y, 0)
            if layer == "lower":
                pygame.draw.line(self.screen, (128, 138, 148), (int(pole_base[0]), int(pole_base[1])), (int(pole_top[0]), int(pole_top[1])), 4)
                self._draw_polyline_segments(lower_points, color, width)
                return
            self._draw_polyline_segments(upper_points, color, width)
            label_anchor = self._world_to_screen(x, y, z + radius / 100 + 0.18)

        if layer == "lower":
            return

        font = pygame.font.Font(None, 24)
        label = font.render(str(gate["id"]), True, color)
        self.screen.blit(label, (int(label_anchor[0] - label.get_width() / 2), int(label_anchor[1] - label.get_height() / 2)))

        if active:
            self._draw_gate_hints(tello, gate, label_anchor)

    def _draw_gate_hints(self, tello, gate, anchor):
        hints = tello.drone.get("race_hints", {})
        if not any(hints.values()):
            return

        measurement = tello.get_race_gate_measurements()
        if not measurement:
            return

        parts = []
        if hints.get("distance"):
            parts.append(f"{measurement['distance_cm']} cm")
        if hints.get("height") and gate.get("type") == "hoop":
            parts.append(f"h {measurement['height_cm']} cm")
        if hints.get("relative"):
            parts.append(f"x {measurement['relative_x_cm']} y {measurement['relative_y_cm']} z {measurement['relative_z_cm']}")
        if not parts:
            return

        font = pygame.font.Font(None, 20)
        rendered = font.render(" | ".join(parts), True, (226, 232, 240))
        x = int(anchor[0] - rendered.get_width() / 2)
        y = int(anchor[1] + 18)
        bg = pygame.Rect(x - 5, y - 3, rendered.get_width() + 10, rendered.get_height() + 6)
        pygame.draw.rect(self.screen, (8, 12, 16), bg, border_radius=3)
        pygame.draw.rect(self.screen, (66, 78, 91), bg, 1, border_radius=3)
        self.screen.blit(rendered, (x, y))

    def _draw_race_gates(self, tello, layer="full"):
        gates = tello.drone.get("race_gates", [])
        next_gate = tello.drone.get("race_next_gate", 0)
        for index, gate in enumerate(gates):
            self._draw_race_gate(tello, gate, active=index == next_gate, layer=layer)

    def _draw_keymap(self):
        if not self.show_keymap:
            return
        font = pygame.font.Font(None, 20)
        lines = [
            "F follow camera",
            "O overview camera",
            "+/- zoom",
            "D distance hint",
            "H height hint",
            "R relative hint",
            "V forward vector",
            "K hide keys",
        ]
        rendered = [font.render(line, True, (214, 222, 232)) for line in lines]
        width = max(item.get_width() for item in rendered) + 18
        height = len(rendered) * 20 + 14
        panel = pygame.Rect(self.width - width - 14, 14, width, height)
        pygame.draw.rect(self.screen, (8, 12, 16), panel, border_radius=4)
        pygame.draw.rect(self.screen, (70, 82, 96), panel, 1, border_radius=4)
        y = panel.y + 8
        for item in rendered:
            self.screen.blit(item, (panel.x + 9, y))
            y += 20

    def _draw_race_timer(self, tello):
        gates = tello.drone.get("race_gates", [])
        if not gates and tello.drone.get("race_timer_start") is None and tello.drone.get("race_final_time_seconds") is None:
            return
        timer = tello.get_race_time()
        font = pygame.font.Font(None, 21)
        status = "running" if timer["running"] else "finished" if tello.drone.get("race_final_time_seconds") is not None else "ready"
        lines = [
            f"Race {status}",
            f"time {timer['elapsed_seconds']:.1f}s  penalty +{timer['penalty_seconds']:.1f}s",
            f"final {timer['final_time_seconds']:.1f}s",
            f"score {timer['score']}  missed {timer['missed_gates']}  wrong {timer['wrong_order_gates']}",
        ]
        rendered = [font.render(line, True, (220, 228, 236)) for line in lines]
        width = max(item.get_width() for item in rendered) + 18
        height = len(rendered) * 21 + 12
        panel = pygame.Rect(14, self.height - height - 14, width, height)
        pygame.draw.rect(self.screen, (8, 12, 16), panel, border_radius=4)
        pygame.draw.rect(self.screen, (70, 82, 96), panel, 1, border_radius=4)
        y = panel.y + 7
        for item in rendered:
            self.screen.blit(item, (panel.x + 9, y))
            y += 21

    def _project_drone_points(self, tello):
        pos = tello.drone["pos"]
        yaw = math.radians(tello.drone["rot"])
        flip_frames = tello.drone.get("flip", 0)
        flip_direction = tello.drone.get("flip_direction", "b")
        flip_angle = ((24 - flip_frames) / 24) * math.tau if flip_frames > 0 else 0

        def point(local):
            x, y = local[0], local[1]
            z = local[2] if len(local) > 2 else 0
            if flip_frames > 0:
                if flip_direction in {"f", "b"}:
                    angle = flip_angle if flip_direction == "f" else -flip_angle
                    y, z = y * math.cos(angle) - z * math.sin(angle), y * math.sin(angle) + z * math.cos(angle)
                else:
                    angle = flip_angle if flip_direction == "l" else -flip_angle
                    x, z = x * math.cos(angle) + z * math.sin(angle), -x * math.sin(angle) + z * math.cos(angle)
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
        pattern = tello.drone.get("mled", "")
        visual_scale = max(0.45, min(2.0, self.camera_zoom))
        cell = max(2, int(4 * visual_scale))
        gap = max(1, int(visual_scale))
        panel_size = 8 * cell + 7 * gap
        panel = pygame.Rect(0, 0, panel_size + 6, panel_size + 6)
        panel.center = (int(body_center[0]), int(body_center[1] - body_height / 2 - panel.height / 2 - 10))

        led_center = (int(body_center[0]), int(panel.y - 12 if pattern else body_center[1] - body_height / 2 - 14))
        if any(led):
            glow = pygame.Surface((54, 54), pygame.SRCALPHA)
            for radius, alpha in ((int(25 * visual_scale), 28), (int(18 * visual_scale), 42), (int(12 * visual_scale), 70)):
                pygame.draw.circle(glow, (*led, alpha), (27, 27), radius)
            self.screen.blit(glow, (led_center[0] - 27, led_center[1] - 27))

        led_radius = max(6, int(12 * visual_scale))
        pygame.draw.circle(self.screen, (12, 14, 16), led_center, led_radius)
        if any(led):
            pygame.draw.circle(self.screen, led, led_center, max(4, int(8 * visual_scale)))
            pygame.draw.circle(self.screen, (245, 250, 255), (led_center[0] - 3, led_center[1] - 3), 2)
        else:
            pygame.draw.circle(self.screen, (46, 52, 58), led_center, max(4, int(8 * visual_scale)), 1)

        if pattern:
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
        visual_scale = max(0.45, min(2.0, self.camera_zoom))
        shadow_radius = max(8, int((44 / (1 + altitude * 0.15)) * visual_scale))
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
        for rotor in rotors:
            pygame.draw.line(self.screen, arm_color, body_center, rotor, 6)

        flip_phase = tello.drone.get("flip", 0)
        flip_direction = tello.drone.get("flip_direction", "b")
        flip_angle = ((24 - flip_phase) / 24) * math.tau if flip_phase > 0 else 0
        body_width = int(58 * visual_scale)
        body_height = int(38 * visual_scale)
        if flip_phase > 0 and flip_direction in {"l", "r"}:
            body_width = max(10, int(body_width * abs(math.cos(flip_angle))))
        elif flip_phase > 0:
            body_height = max(8, int(body_height * abs(math.cos(flip_angle))))

        if flip_phase > 0:
            body = [
                point((-32, -22, 0)),
                point((32, -22, 0)),
                point((32, 22, 0)),
                point((-32, 22, 0)),
            ]
            pygame.draw.polygon(self.screen, (53, 67, 77), body)
            pygame.draw.lines(self.screen, (211, 218, 224), True, body, 2)
        else:
            body_rect = pygame.Rect(0, 0, body_width, body_height)
            body_rect.center = (int(body_center[0]), int(body_center[1]))
            pygame.draw.ellipse(self.screen, (53, 67, 77), body_rect)
            pygame.draw.ellipse(self.screen, (211, 218, 224), body_rect, 2)
        nose = point((0, 34, 0))
        pygame.draw.circle(self.screen, (240, 246, 252), (int(nose[0]), int(nose[1])), max(2, int(3 * visual_scale)))
        self._draw_expansion_kit(tello, body_center, body_width, body_height)

        for rotor in rotors:
            self._draw_rotor((int(rotor[0]), int(rotor[1])), max(7, int(17 * visual_scale)))

        if tello.drone.get("race_hints", {}).get("forward"):
            yaw = math.radians(tello.drone["rot"])
            start = self._world_to_screen(pos[0], pos[1], pos[2] + 0.05)
            end = self._world_to_screen(pos[0] + math.sin(yaw) * 180, pos[1] + math.cos(yaw) * 180, pos[2] + 0.05)
            pygame.draw.line(self.screen, (248, 250, 252), start, end, 3)
            pygame.draw.circle(self.screen, (248, 250, 252), (int(end[0]), int(end[1])), 5)

        top = self._world_to_screen(pos[0], pos[1], pos[2])
        ground = self._world_to_screen(pos[0], pos[1], 0)
        pygame.draw.line(self.screen, ALTITUDE_COLOR, (top[0] - 40, top[1]), (ground[0] - 40, ground[1]), 2)
        height_cm = int(max(0, (pos[2] - 1.0) * 100))
        font = pygame.font.Font(None, 22)
        label = font.render(f"{height_cm} cm", True, ALTITUDE_COLOR)
        self.screen.blit(label, (top[0] - 30, top[1] - 24))

    def _draw_race_summary_popup(self, tello):
        if not tello.drone.get("race_show_summary"):
            return
        timer = tello.get_race_time()
        font = pygame.font.Font(None, 28)
        small = pygame.font.Font(None, 22)
        lines = [
            "Race finished",
            f"Time: {timer['elapsed_seconds']:.1f}s",
            f"Penalty: +{timer['penalty_seconds']:.1f}s",
            f"Final: {timer['final_time_seconds']:.1f}s",
            f"Score: {timer['score']}",
        ]
        rendered = [font.render(lines[0], True, (248, 250, 252))]
        rendered.extend(small.render(line, True, (226, 232, 240)) for line in lines[1:])
        width = max(item.get_width() for item in rendered) + 70
        height = 190
        panel = pygame.Rect(0, 0, width, height)
        panel.center = (self.width // 2, self.height // 2)
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 92))
        self.screen.blit(overlay, (0, 0))
        pygame.draw.rect(self.screen, (12, 18, 24), panel, border_radius=6)
        pygame.draw.rect(self.screen, (100, 116, 139), panel, 1, border_radius=6)
        y = panel.y + 20
        for item in rendered:
            self.screen.blit(item, (panel.centerx - item.get_width() / 2, y))
            y += 28

        close_rect = pygame.Rect(panel.x + 28, panel.bottom - 48, 86, 30)
        again_rect = pygame.Rect(panel.right - 114, panel.bottom - 48, 86, 30)
        self.summary_buttons = [(close_rect, "close", tello), (again_rect, "again", tello)]
        for rect, label in ((close_rect, "Close"), (again_rect, "Again")):
            pygame.draw.rect(self.screen, (30, 41, 59), rect, border_radius=4)
            pygame.draw.rect(self.screen, (148, 163, 184), rect, 1, border_radius=4)
            text = small.render(label, True, (248, 250, 252))
            self.screen.blit(text, (rect.centerx - text.get_width() / 2, rect.centery - text.get_height() / 2))

    def render_frame(self, windAmt=0.3, apply_wind=True):
        """Draw one simulator frame."""
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

        with self._lock:
            tellos = list(self.tellos)

        self._update_camera(tellos)
        self.summary_buttons = []

        self.screen.fill(BACKGROUND)
        self._draw_grid()

        for tello in tellos:
            if apply_wind and tello.is_flying and tello.is_windy:
                tello.drone["pos"][0] += self._noise_x
                tello.drone["pos"][1] += self._noise_y
                tello.drone["pos"][2] = max(1.0, tello.drone["pos"][2] + self._noise_z * 0.01)
                tello.drone["rot"] += self._noise_t * 0.03

            tello._update_race_gate_progress()
            self._draw_race_curve(tello)
            self._draw_race_gates(tello, layer="shadow")
            self._draw_race_gates(tello, layer="lower")

            tello.flightPathTaken.append(tuple(tello.drone["pos"]))
            if len(tello.flightPathTaken) > 2000:
                tello.flightPathTaken = tello.flightPathTaken[-1000:]

            if SHOW_TRAILS:
                for path in tello.flightPathTaken:
                    pygame.draw.circle(self.screen, (130, 140, 148), self._world_to_screen(path[0], path[1], 0), 2)

            self._draw_drone_3d(tello)
            self._draw_race_gates(tello, layer="upper")
            self._draw_race_timer(tello)
            self._draw_race_summary_popup(tello)

            if tello.drone.get("flip", 0) > 0:
                tello.drone["flip"] -= 1

        self._draw_keymap()
        pygame.display.flip()

    def update_visual(self, windAmt=0.3):
        """Continuously render simulator frames."""
        while self.running:
            self.render_frame(windAmt=windAmt)
            time.sleep(1 / 60)
