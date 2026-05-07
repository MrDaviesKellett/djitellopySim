import logging
import math
import time
from collections import deque
from queue import Queue
from random import Random, randint, uniform
from threading import Barrier, Lock, Thread
from typing import Callable, Dict, List, Optional, Union

import numpy as np

from physicsSim import sim

PI = math.pi
SIMULATION = None
RACE_HOOP_RADIUS_CM = 110
RACE_ARCH_RADIUS_CM = 300
RACE_MAX_TURN_DEGREES = 110


class TelloException(Exception):
    pass


class BackgroundFrameRead:
    def __init__(self, tello, with_queue=False, maxsize=32):
        """Create and initialise this object."""
        self.tello = tello
        self.with_queue = with_queue
        self.frames = deque([], maxsize)
        self.lock = Lock()
        self.stopped = False
        self._frame = self._make_frame()
        self.worker = Thread(target=self.update_frame, daemon=True)

    def _make_frame(self):
        frame = np.zeros((300, 400, 3), dtype=np.uint8)
        height = int(self.tello.get_height())
        battery = int(self.tello.get_battery())
        frame[:, :, 0] = min(255, height)
        frame[:, :, 1] = max(0, min(255, battery * 2))
        frame[:, :, 2] = 80 if self.tello.stream_on else 20
        return frame

    def start(self):
        """Start background work and return this object when appropriate."""
        self.worker.start()

    def update_frame(self):
        """Continuously update the simulated video frame."""
        while not self.stopped:
            frame = self._make_frame()
            if self.with_queue:
                with self.lock:
                    self.frames.append(frame)
            else:
                self.frame = frame
            time.sleep(1 / 30)

    def get_queued_frame(self):
        """Return the next queued frame, or None when the queue is empty."""
        with self.lock:
            try:
                return self.frames.popleft()
            except IndexError:
                return None

    @property
    def frame(self):
        """Return the latest simulated video frame."""
        if self.with_queue:
            return self.get_queued_frame()
        with self.lock:
            return self._frame

    @frame.setter
    def frame(self, value):
        """Return the latest simulated video frame."""
        with self.lock:
            self._frame = value

    def stop(self):
        """Stop background frame reading."""
        self.stopped = True


class Tello:
    RESPONSE_TIMEOUT = 7
    TAKEOFF_TIMEOUT = 20
    FRAME_GRAB_TIMEOUT = 5
    TIME_BTW_COMMANDS = 0.1
    TIME_BTW_RC_CONTROL_COMMANDS = 0.001
    RETRY_COUNT = 3
    TELLO_IP = "192.168.10.1"

    VS_UDP_IP = "0.0.0.0"
    VS_UDP_PORT = 11111
    CONTROL_UDP_PORT = 8889
    STATE_UDP_PORT = 8890

    BITRATE_AUTO = 0
    BITRATE_1MBPS = 1
    BITRATE_2MBPS = 2
    BITRATE_3MBPS = 3
    BITRATE_4MBPS = 4
    BITRATE_5MBPS = 5
    RESOLUTION_480P = "low"
    RESOLUTION_720P = "high"
    FPS_5 = "low"
    FPS_15 = "middle"
    FPS_30 = "high"
    CAMERA_FORWARD = 0
    CAMERA_DOWNWARD = 1

    HANDLER = logging.StreamHandler()
    FORMATTER = logging.Formatter("[%(levelname)s] %(filename)s - %(lineno)d - %(message)s")
    HANDLER.setFormatter(FORMATTER)
    LOGGER = logging.getLogger("djitellopy simulator")
    if not LOGGER.handlers:
        LOGGER.addHandler(HANDLER)
    LOGGER.setLevel(logging.INFO)

    INT_STATE_FIELDS = (
        "mid", "x", "y", "z", "pitch", "roll", "yaw", "vgx", "vgy", "vgz",
        "templ", "temph", "tof", "h", "bat", "time",
    )
    FLOAT_STATE_FIELDS = ("baro", "agx", "agy", "agz")
    state_field_converters: Dict[str, Union[type, type]] = {key: int for key in INT_STATE_FIELDS}
    state_field_converters.update({key: float for key in FLOAT_STATE_FIELDS})

    def __init__(self, host=TELLO_IP, retry_count=RETRY_COUNT, vs_udp=VS_UDP_PORT, swarm=False, start_visual=True):
        """Create and initialise this object."""
        global SIMULATION
        self.flightPathTaken = []
        self.address = (host, Tello.CONTROL_UDP_PORT)
        self.retry_count = retry_count
        self.vs_udp_port = vs_udp
        self.swarm = swarm
        self.stream_on = False
        self.background_frame_read: Optional[BackgroundFrameRead] = None
        self.last_received_command_timestamp = time.time()
        self.last_rc_control_timestamp = time.time()
        self.is_flying = False
        self.is_windy = True
        self.is_latency = True
        self._connected = False
        self._motors_on = False
        self._start_time = None
        self._last_state_update = time.time()
        self._last_pos = [500.0, 400.0, 1.0]

        if SIMULATION is None and start_visual:
            SIMULATION = sim()
        self.simulation = SIMULATION

        self.drone = {
            "scl": 0.08,
            "pos": [500.0, 400.0, 1.0],
            "rot": 0.0,
            "pitch": 0.0,
            "roll": 0.0,
            "speed": 100,
            "flip": 0,
            "flip_direction": "b",
            "led": (0, 0, 0),
            "mled": "",
            "battery": 100,
            "temperature": 42,
            "barometer": 1.0,
            "mission_pads": False,
            "mission_pad_direction": 0,
            "video_bitrate": Tello.BITRATE_AUTO,
            "video_resolution": Tello.RESOLUTION_720P,
            "video_fps": Tello.FPS_30,
            "video_direction": Tello.CAMERA_FORWARD,
            "wifi_snr": "90",
            "serial_number": "SIM000000000",
            "sdk_version": "3.0",
            "race_gates": [],
            "race_next_gate": 0,
            "race_completed": False,
            "race_last_pos": [500.0, 400.0, 1.0],
            "race_hints": {"distance": True, "height": False, "relative": False, "forward": False},
            "race_timer_start": None,
            "race_elapsed_seconds": 0.0,
            "race_penalty_seconds": 0.0,
            "race_missed_gates": 0,
            "race_wrong_order_gates": 0,
            "race_final_time_seconds": None,
            "race_score": 0,
            "race_show_summary": False,
        }
        self._state = {}
        self._update_state()

        Tello.LOGGER.info("Tello instance was initialized. Host: '%s'. Port: '%s'.", host, Tello.CONTROL_UDP_PORT)
        if self.simulation is not None:
            self.simulation.register(self)
            self._render_frame(apply_wind=False)

    def _setSwarmPos(self, i):
        self.drone["pos"][0] += -260 + 130 * (i % 4)
        self.drone["pos"][1] += -260 + 130 * (i // 4)
        self._last_pos = list(self.drone["pos"])
        self._update_state()

    def _simulate_latency(self, min_delay=0.1, max_delay=0.5):
        if self.is_latency:
            self._sleep_with_visual(uniform(min_delay, max_delay))

    def simLat(self, min=0.1, max=0.5):
        """Add simulated command latency between the given minimum and maximum seconds."""
        self._simulate_latency(min, max)

    def _render_frame(self, apply_wind=True):
        if self.simulation is not None:
            self._update_race_gate_progress()
            self.simulation.render_frame(apply_wind=apply_wind)

    def setup_race_gates(
        self,
        count: int = 5,
        course: str = "line",
        seed: Optional[int] = None,
        min_randomness: float = 0,
        max_randomness: float = 35,
    ):
        """Create a flyable race-gate course and return the generated gates."""
        if isinstance(course, int) and seed is None:
            seed = course
            course = "line"
        rng = Random(seed)
        count = max(1, min(12, int(count)))
        start = self.drone["pos"]
        course = str(course).lower()
        if course == "random":
            course = rng.choice(["line", "slalom", "loop", "climb", "arches", "mixed"])
        if course not in {"line", "slalom", "loop", "climb", "arches", "mixed"}:
            course = "line"

        gates = []
        min_randomness = max(0.0, float(min_randomness))
        max_randomness = max(min_randomness, float(max_randomness))

        for _ in range(30):
            gates = self._generate_race_course(count, course, rng, start, min_randomness, max_randomness)
            if self._race_course_max_turn_degrees(gates) <= RACE_MAX_TURN_DEGREES:
                break

        self._align_gate_yaws_to_course(gates)

        self.drone["race_gates"] = gates
        self.drone["race_curve"] = self._race_course_curve(gates)
        self.drone["race_max_turn_degrees"] = self._race_course_max_turn_degrees(gates)
        self.drone["race_next_gate"] = 0
        self.drone["race_completed"] = False
        self.drone["race_last_pos"] = list(self.drone["pos"])
        self._reset_race_timer()
        self._render_frame(apply_wind=False)
        return gates

    def _generate_race_course(self, count, course, rng, start, min_randomness, max_randomness):
        templates = {
            "line": [(420, 0), (840, 0), (1260, 0), (1680, 0), (2100, 0), (2520, 0), (2940, 0), (3360, 0)],
            "slalom": [(450, -170), (900, 170), (1350, -170), (1800, 170), (2250, -170), (2700, 170), (3150, -120), (3600, 0)],
            "loop": [(520, 0), (760, 420), (520, 820), (40, 980), (-430, 760), (-650, 320), (-460, -160), (20, -390), (500, -220), (720, 240)],
            "climb": [(430, -100), (860, 80), (1290, -80), (1720, 105), (2150, -50), (2580, 120), (3010, 0), (3440, 80)],
            "arches": [(760, 0), (1520, 0), (2280, 0), (3040, 0), (3800, 220), (4560, 220), (5320, 40), (6080, -180)],
            "mixed": [(520, -170), (1040, 160), (1660, -150), (2240, 170), (2860, -80), (3440, 220), (4060, 0), (4640, -170)],
        }
        offsets = templates[course]
        course_yaw = math.radians(self.drone["rot"])
        forward_x, forward_y = math.sin(course_yaw), math.cos(course_yaw)
        right_x, right_y = math.sin(course_yaw + math.pi / 2), math.cos(course_yaw + math.pi / 2)
        base_z = max(2.7, min(3.3, start[2] + 1.0 if start[2] > 1.2 else 2.9))
        previous = [start[0], start[1]]
        gates = []

        for index in range(count):
            forward, right = offsets[index % len(offsets)]
            gate_type = "hoop"
            if course == "arches":
                gate_type = "arch"
            elif course == "mixed":
                gate_type = "arch" if index % 3 == 2 else "hoop"

            jitter = rng.uniform(min_randomness, max_randomness)
            if rng.choice([True, False]):
                jitter = -jitter
            x = start[0] + forward * forward_x + right * right_x + jitter
            jitter = rng.uniform(min_randomness, max_randomness)
            if rng.choice([True, False]):
                jitter = -jitter
            y = start[1] + forward * forward_y + right * right_y + jitter
            heading = math.atan2(x - previous[0], y - previous[1])

            if gate_type == "arch":
                z = 1.0
            elif course == "climb":
                z = 2.7 + (index % 5) * 0.22
            elif course != "climb":
                z = max(2.65, min(3.35, base_z + rng.uniform(-0.2, 0.2)))

            gates.append({
                "id": index + 1,
                "pos": [float(x), float(y), float(z)],
                "yaw": math.degrees(heading) % 360,
                "type": gate_type,
                "radius": RACE_HOOP_RADIUS_CM if gate_type == "hoop" else RACE_ARCH_RADIUS_CM,
                "passed": False,
                "wrong_order": False,
            })
            previous = [x, y]
        return gates

    def _align_gate_yaws_to_course(self, gates):
        if not gates:
            return
        for index, gate in enumerate(gates):
            if len(gates) == 1:
                continue
            if index == 0:
                before = gate["pos"]
                after = gates[index + 1]["pos"]
            elif index == len(gates) - 1:
                before = gates[index - 1]["pos"]
                after = gate["pos"]
            else:
                before = gates[index - 1]["pos"]
                after = gates[index + 1]["pos"]
            gate["yaw"] = math.degrees(math.atan2(after[0] - before[0], after[1] - before[1])) % 360

    def _race_course_curve(self, gates, samples_per_segment=12):
        points = [gate["pos"] for gate in gates]
        if len(points) < 2:
            return [list(point) for point in points]
        curve = []
        for index in range(len(points) - 1):
            p0 = points[max(0, index - 1)]
            p1 = points[index]
            p2 = points[index + 1]
            p3 = points[min(len(points) - 1, index + 2)]
            for step in range(samples_per_segment):
                t = step / samples_per_segment
                t2 = t * t
                t3 = t2 * t
                curve.append([
                    0.5 * ((2 * p1[axis]) + (-p0[axis] + p2[axis]) * t + (2 * p0[axis] - 5 * p1[axis] + 4 * p2[axis] - p3[axis]) * t2 + (-p0[axis] + 3 * p1[axis] - 3 * p2[axis] + p3[axis]) * t3)
                    for axis in range(3)
                ])
        curve.append(list(points[-1]))
        return curve

    def _race_course_max_turn_degrees(self, gates):
        points = [gate["pos"] for gate in gates]
        if len(points) < 3:
            return 0.0
        max_turn = 0.0
        for index in range(1, len(points) - 1):
            ax = points[index][0] - points[index - 1][0]
            ay = points[index][1] - points[index - 1][1]
            bx = points[index + 1][0] - points[index][0]
            by = points[index + 1][1] - points[index][1]
            a_len = math.hypot(ax, ay)
            b_len = math.hypot(bx, by)
            if a_len == 0 or b_len == 0:
                continue
            dot = max(-1.0, min(1.0, (ax * bx + ay * by) / (a_len * b_len)))
            max_turn = max(max_turn, math.degrees(math.acos(dot)))
        return max_turn

    def set_race_hints(
        self,
        distance: Optional[bool] = None,
        height: Optional[bool] = None,
        relative: Optional[bool] = None,
        forward: Optional[bool] = None,
    ):
        """Show or hide in-view race hints such as distance, height, and heading."""
        hints = dict(self.drone.get("race_hints", {}))
        for key, value in {"distance": distance, "height": height, "relative": relative, "forward": forward}.items():
            if value is not None:
                hints[key] = bool(value)
        self.drone["race_hints"] = hints
        self._render_frame(apply_wind=False)

    def set_camera_follow(self, enabled=True):
        """Turn the simulator follow camera on or off."""
        if self.simulation is not None:
            self.simulation.set_camera_follow(enabled)
            if enabled:
                self.simulation.camera_x = self.drone["pos"][0]
                self.simulation.camera_y = self.drone["pos"][1]
                self.simulation.camera_z = self.drone["pos"][2]
            self._render_frame(apply_wind=False)

    def set_camera_overview(self):
        """Switch the simulator camera to a zoomed-out course overview."""
        if self.simulation is not None:
            self.simulation.set_camera_overview()
            self._render_frame(apply_wind=False)

    def clear_race_gates(self):
        """Remove all race gates and reset race progress."""
        self.drone["race_gates"] = []
        self.drone["race_curve"] = []
        self.drone["race_next_gate"] = 0
        self.drone["race_completed"] = False
        self.drone["race_last_pos"] = list(self.drone["pos"])
        self._reset_race_timer()
        self._render_frame(apply_wind=False)

    def get_race_gates(self):
        """Return the generated race gates."""
        return list(self.drone.get("race_gates", []))

    def get_next_race_gate(self):
        """Return the next race gate the drone should pass through."""
        gates = self.drone.get("race_gates", [])
        next_index = self.drone.get("race_next_gate", 0)
        if next_index >= len(gates):
            return None
        return gates[next_index]

    def get_race_gate_measurements(self):
        """Return distance and angle measurements from the drone to the next gate."""
        gate = self.get_next_race_gate()
        if gate is None:
            return None
        return self.measure_drone_to_gate(gate["id"])

    def measure_drone_to_gate(self, gate_id=None):
        """Measure distance and angle from the drone to one race gate."""
        gates = self.drone.get("race_gates", [])
        if not gates:
            return None
        if gate_id is None:
            gate = self.get_next_race_gate()
        else:
            gate = next((item for item in gates if item["id"] == gate_id), None)
        if gate is None:
            return None
        return self._race_gate_measurement(gate)

    def measure_gate_to_gate(self, from_gate_id, to_gate_id=None):
        """Measure distance and turn angle from one race gate to another."""
        gates = self.drone.get("race_gates", [])
        from_gate = next((item for item in gates if item["id"] == from_gate_id), None)
        if from_gate is None:
            return None
        if to_gate_id is None:
            to_gate_id = from_gate_id + 1
        to_gate = next((item for item in gates if item["id"] == to_gate_id), None)
        if to_gate is None:
            return None
        dx = to_gate["pos"][0] - from_gate["pos"][0]
        dy = to_gate["pos"][1] - from_gate["pos"][1]
        dz_cm = (to_gate["pos"][2] - from_gate["pos"][2]) * 100
        heading = math.degrees(math.atan2(dx, dy)) % 360
        relative_angle = ((heading - from_gate["yaw"] + 180) % 360) - 180
        return {
            "from_gate": from_gate["id"],
            "to_gate": to_gate["id"],
            "distance_cm": int(round(math.sqrt(dx * dx + dy * dy + dz_cm * dz_cm))),
            "flat_distance_cm": int(round(math.hypot(dx, dy))),
            "relative_x_cm": int(round(dx)),
            "relative_y_cm": int(round(dy)),
            "relative_z_cm": int(round(dz_cm)),
            "heading_degrees": int(round(heading)),
            "angle_from_gate_forward_degrees": int(round(relative_angle)),
        }

    def _race_gate_measurement(self, gate, pos=None):
        pos = self.drone["pos"] if pos is None else pos
        yaw = math.radians(gate["yaw"])
        dx = pos[0] - gate["pos"][0]
        dy = pos[1] - gate["pos"][1]
        dz_cm = int(round((pos[2] - gate["pos"][2]) * 100))
        to_gate_x = gate["pos"][0] - pos[0]
        to_gate_y = gate["pos"][1] - pos[1]
        heading = math.degrees(math.atan2(to_gate_x, to_gate_y)) % 360
        angle_from_drone = ((heading - self.drone["rot"] + 180) % 360) - 180
        ahead_cm = int(round(dx * math.sin(yaw) + dy * math.cos(yaw)))
        side_cm = int(round(dx * math.cos(yaw) - dy * math.sin(yaw)))
        return {
            "gate": gate["id"],
            "height_cm": int(round((gate["pos"][2] - 1.0) * 100)),
            "relative_x_cm": int(round(gate["pos"][0] - pos[0])),
            "relative_y_cm": int(round(gate["pos"][1] - pos[1])),
            "relative_z_cm": int(round((gate["pos"][2] - pos[2]) * 100)),
            "ahead_cm": ahead_cm,
            "side_cm": side_cm,
            "vertical_cm": dz_cm,
            "distance_cm": int(round(math.sqrt(dx * dx + dy * dy + dz_cm * dz_cm))),
            "flat_distance_cm": int(round(math.hypot(dx, dy))),
            "heading_degrees": int(round(heading)),
            "angle_from_drone_forward_degrees": int(round(angle_from_drone)),
            "yaw_degrees": int(round(gate["yaw"])),
            "type": gate.get("type", "hoop"),
            "radius_cm": gate.get("radius", RACE_HOOP_RADIUS_CM),
        }

    def _update_race_gate_progress(self):
        gates = self.drone.get("race_gates", [])
        next_index = self.drone.get("race_next_gate", 0)
        if not gates or next_index >= len(gates):
            self.drone["race_last_pos"] = list(self.drone["pos"])
            return

        previous = self.drone.get("race_last_pos", self.drone["pos"])
        current = self.drone["pos"]

        for index, gate in enumerate(gates):
            if gate.get("passed"):
                continue
            if not self._crossed_gate_opening(gate, previous, current):
                continue
            if index == next_index:
                gate["passed"] = True
                self.drone["race_score"] += 100
                next_index += 1
                self.drone["race_next_gate"] = next_index
                self.drone["race_completed"] = next_index >= len(gates)
            elif index > next_index and not gate.get("wrong_order"):
                gate["wrong_order"] = True
                self.drone["race_wrong_order_gates"] += 1
                self.drone["race_penalty_seconds"] += 5
                self.drone["race_score"] -= 50

        self.drone["race_last_pos"] = list(current)

    def _crossed_gate_opening(self, gate, previous, current):
        prev_measure = self._race_gate_measurement(gate, previous)
        current_measure = self._race_gate_measurement(gate, current)
        if not (prev_measure["ahead_cm"] < 0 <= current_measure["ahead_cm"]):
            return False
        radius = gate.get("radius", RACE_HOOP_RADIUS_CM)
        if gate.get("type") == "arch":
            return current_measure["vertical_cm"] >= 0 and math.hypot(current_measure["side_cm"], current_measure["vertical_cm"]) <= radius
        return math.hypot(current_measure["side_cm"], current_measure["vertical_cm"]) <= radius

    def _reset_race_timer(self):
        self.drone["race_timer_start"] = None
        self.drone["race_elapsed_seconds"] = 0.0
        self.drone["race_penalty_seconds"] = 0.0
        self.drone["race_missed_gates"] = 0
        self.drone["race_wrong_order_gates"] = 0
        self.drone["race_final_time_seconds"] = None
        self.drone["race_score"] = 0
        self.drone["race_show_summary"] = False
        for gate in self.drone.get("race_gates", []):
            gate["passed"] = False
            gate["wrong_order"] = False

    def _start_race_timer(self):
        self._reset_race_timer()
        self.drone["race_next_gate"] = 0
        self.drone["race_completed"] = False
        self.drone["race_last_pos"] = list(self.drone["pos"])
        self.drone["race_timer_start"] = time.time()

    def _finish_race_timer(self):
        start = self.drone.get("race_timer_start")
        if start is None:
            return
        elapsed = time.time() - start
        missed = sum(1 for gate in self.drone.get("race_gates", []) if not gate.get("passed"))
        penalty = self.drone.get("race_penalty_seconds", 0.0) + missed * 10
        self.drone["race_elapsed_seconds"] = elapsed
        self.drone["race_missed_gates"] = missed
        self.drone["race_penalty_seconds"] = penalty
        self.drone["race_final_time_seconds"] = elapsed + penalty
        self.drone["race_score"] -= missed * 100
        self.drone["race_show_summary"] = True
        self.drone["race_timer_start"] = None

    def get_race_time(self):
        """Return race timing, penalties, and score information."""
        start = self.drone.get("race_timer_start")
        elapsed = (time.time() - start) if start is not None else self.drone.get("race_elapsed_seconds", 0.0)
        penalty = self.drone.get("race_penalty_seconds", 0.0)
        final_time = self.drone.get("race_final_time_seconds")
        return {
            "running": start is not None,
            "elapsed_seconds": elapsed,
            "penalty_seconds": penalty,
            "missed_gates": self.drone.get("race_missed_gates", 0),
            "wrong_order_gates": self.drone.get("race_wrong_order_gates", 0),
            "score": self.drone.get("race_score", 0),
            "final_time_seconds": elapsed + penalty if final_time is None else final_time,
        }

    def _sleep_with_visual(self, seconds):
        end = time.time() + seconds
        while time.time() < end:
            self._render_frame()
            time.sleep(min(1 / 60, max(end - time.time(), 0)))

    def _flight_time(self):
        if self._start_time is None:
            return 0
        return int(time.time() - self._start_time)

    def _update_state(self):
        now = time.time()
        elapsed = max(now - self._last_state_update, 0.001)
        pos = self.drone["pos"]
        old = self._last_pos
        vgx = int((pos[0] - old[0]) / elapsed)
        vgy = int((pos[1] - old[1]) / elapsed)
        vgz = int(((pos[2] - old[2]) * 100) / elapsed)
        self._last_pos = list(pos)
        self._last_state_update = now

        height = max(0, int((pos[2] - 1.0) * 100))
        self._state = {
            "mid": -1 if not self.drone["mission_pads"] else 1,
            "x": 0,
            "y": 0,
            "z": height,
            "pitch": int(self.drone.get("pitch", 0)),
            "roll": int(self.drone.get("roll", 0)),
            "yaw": int((-self.drone["rot"]) % 360),
            "vgx": vgx,
            "vgy": vgy,
            "vgz": vgz,
            "templ": self.drone["temperature"] - 2,
            "temph": self.drone["temperature"] + 2,
            "tof": height,
            "h": height,
            "bat": max(0, int(self.drone["battery"])),
            "baro": float(self.drone["barometer"] + height / 100),
            "time": self._flight_time(),
            "agx": 0.0,
            "agy": 0.0,
            "agz": -9.8 if self.is_flying else 0.0,
        }
        return self._state

    @staticmethod
    def parse_state(state: str) -> Dict[str, Union[int, float, str]]:
        """Convert a Tello state string into a dictionary."""
        state = state.strip()
        if state == "ok":
            return {}
        state_dict = {}
        for field in state.split(";"):
            split = field.split(":")
            if len(split) < 2:
                continue
            key = split[0]
            value = split[1]
            converter = Tello.state_field_converters.get(key)
            if converter:
                try:
                    value = converter(value)
                except ValueError:
                    continue
            state_dict[key] = value
        return state_dict

    def get_own_udp_object(self):
        """Return the simulator UDP object placeholder."""
        return {"responses": [], "state": self.get_current_state()}

    def get_current_state(self) -> dict:
        """Return the latest simulated drone state dictionary."""
        return dict(self._update_state())

    def get_state_field(self, key: str):
        """Return one field from the latest simulated state."""
        state = self.get_current_state()
        if key not in state:
            raise TelloException(f"Could not get state property: {key}")
        return state[key]

    def send_command_with_return(self, command: str, timeout: int = RESPONSE_TIMEOUT) -> str:
        """Send a command string and return the simulator response."""
        diff = time.time() - self.last_received_command_timestamp
        if diff < self.TIME_BTW_COMMANDS:
            time.sleep(diff)
        self.LOGGER.info("Send command: '%s'", command)
        response = self._handle_command(command, expect_response=True)
        self.last_received_command_timestamp = time.time()
        self.LOGGER.info("Response %s: '%s'", command, response)
        return response

    def send_command_without_return(self, command: str):
        """Send a command string without waiting for a response."""
        self.LOGGER.info("Send command (no response expected): '%s'", command)
        self._handle_command(command, expect_response=False)

    def send_control_command(self, command: str, timeout: int = RESPONSE_TIMEOUT) -> bool:
        """Send a command that should return ok and report success as a boolean."""
        response = "max retries exceeded"
        for _ in range(self.retry_count):
            response = self.send_command_with_return(command, timeout=timeout)
            if "ok" in response.lower():
                return True
        self.raise_result_error(command, response)
        return False

    def send_read_command(self, command: str) -> str:
        """Send a read command and return its text response."""
        response = str(self.send_command_with_return(command))
        if any(word in response for word in ("error", "ERROR", "False")):
            self.raise_result_error(command, response)
        return response

    def send_read_command_int(self, command: str) -> int:
        """Send a read command and return its response as an integer."""
        return int(self.send_read_command(command))

    def send_read_command_float(self, command: str) -> float:
        """Send a read command and return its response as a float."""
        return float(self.send_read_command(command))

    def raise_result_error(self, command: str, response: str) -> bool:
        """Raise TelloException if a command response is not ok."""
        tries = 1 + self.retry_count
        raise TelloException(f"Command '{command}' was unsuccessful for {tries} tries. Latest response:\t'{response}'")

    def _handle_command(self, command: str, expect_response=True):
        parts = command.strip().split()
        if not parts:
            return "error"
        op = parts[0].lower()
        try:
            if op == "command":
                self._connected = True
            elif op == "takeoff":
                self.takeoff()
            elif op == "land":
                self.land(close_window=False)
            elif op in {"up", "down", "left", "right", "forward", "back"}:
                self.move(op, int(parts[1]))
            elif op in {"cw", "ccw"}:
                self.rotate(op, int(parts[1]))
            elif op == "flip":
                self.flip(parts[1])
            elif op == "go":
                self._go_command(parts)
            elif op == "curve":
                self._curve_command(parts)
            elif op == "jump":
                self.go_xyz_speed_yaw_mid(int(parts[1]), int(parts[2]), int(parts[3]), int(parts[4]), int(parts[5]), int(parts[6][1:]), int(parts[7][1:]))
            elif op == "speed":
                self.drone["speed"] = int(parts[1])
            elif op == "rc":
                self._apply_rc(*(int(v) for v in parts[1:5]))
            elif op == "streamon":
                self.stream_on = True
            elif op == "streamoff":
                self.stream_on = False
            elif op == "emergency":
                self.is_flying = False
                self._motors_on = False
            elif op == "keepalive":
                pass
            elif op == "motoron":
                self._motors_on = True
            elif op == "motoroff":
                self._motors_on = False
            elif op == "throwfly":
                self.is_flying = True
                self._start_time = self._start_time or time.time()
            elif op == "mon":
                self.drone["mission_pads"] = True
            elif op == "moff":
                self.drone["mission_pads"] = False
            elif op == "mdirection":
                self.drone["mission_pad_direction"] = int(parts[1])
            elif op in {"wifi", "ap", "port", "reboot"}:
                pass
            elif op == "setbitrate":
                self.drone["video_bitrate"] = int(parts[1])
            elif op == "setresolution":
                self.drone["video_resolution"] = parts[1]
            elif op == "setfps":
                self.drone["video_fps"] = parts[1]
            elif op == "downvision":
                self.drone["video_direction"] = int(parts[1])
            elif op == "ext":
                self._handle_expansion(parts[1:])
            elif op == "racegates":
                count = int(parts[1]) if len(parts) > 1 else 5
                course = "line"
                seed = None
                min_randomness = 0
                max_randomness = 35
                if len(parts) > 2:
                    try:
                        seed = int(parts[2])
                    except ValueError:
                        course = parts[2]
                if len(parts) > 3:
                    seed = int(parts[3])
                if len(parts) > 4:
                    min_randomness = float(parts[4])
                if len(parts) > 5:
                    max_randomness = float(parts[5])
                self.setup_race_gates(count, course, seed, min_randomness, max_randomness)
            elif op == "cleargates":
                self.clear_race_gates()
            elif op == "racehints":
                self._handle_race_hints(parts[1:])
            elif op == "camerafollow":
                enabled = len(parts) < 2 or parts[1].lower() in {"1", "true", "on", "yes"}
                self.set_camera_follow(enabled)
            elif op == "cameraoverview":
                self.set_camera_overview()
            elif command.endswith("?"):
                return self._query(command)
            else:
                return "error Unknown command"
        except (IndexError, ValueError):
            return "error"
        self._update_state()
        return "ok" if expect_response else None

    def _query(self, command):
        state = self.get_current_state()
        queries = {
            "speed?": str(self.drone["speed"]),
            "battery?": str(state["bat"]),
            "time?": str(state["time"]),
            "height?": str(state["h"]),
            "temp?": str(int(self.get_temperature())),
            "baro?": str(int(state["baro"])),
            "tof?": f"{int(state['tof'] * 10)}mm",
            "wifi?": self.drone["wifi_snr"],
            "sdk?": self.drone["sdk_version"],
            "sn?": self.drone["serial_number"],
            "active?": "active" if self._connected else "inactive",
            "attitude?": f"pitch:{state['pitch']};roll:{state['roll']};yaw:{state['yaw']};",
        }
        return queries.get(command, "error Unknown query")

    def _handle_expansion(self, parts):
        if not parts:
            return
        if parts[0].lower() == "led" and len(parts) >= 4:
            self.drone["led"] = tuple(max(0, min(255, int(v))) for v in parts[1:4])
        elif parts[0].lower() == "mled":
            pattern = "".join(parts[2:]) if len(parts) >= 3 and len("".join(parts[2:])) >= 64 else "".join(parts[1:])
            self.drone["mled"] = pattern[:64].ljust(64, "0")

    def _handle_race_hints(self, parts):
        if not parts:
            return
        hints = dict(self.drone.get("race_hints", {}))
        if parts[0].lower() == "off":
            hints = {key: False for key in hints}
        elif parts[0].lower() == "on":
            hints = {key: True for key in hints}
        else:
            value = True
            if len(parts) > 1:
                value = parts[1].lower() in {"1", "true", "on", "yes"}
            if parts[0].lower() in hints:
                hints[parts[0].lower()] = value
        self.drone["race_hints"] = hints

    def connect(self, wait_for_state=True):
        """Connect to the simulated drone command interface."""
        self._connected = True
        self.send_control_command("command")
        if wait_for_state:
            time.sleep(randint(1, 5) / 20)
            Tello.LOGGER.debug("'.connect()' received first state packet")

    def send_keepalive(self):
        """Send a simulated keepalive command."""
        self.send_control_command("keepalive")

    def turn_motor_on(self):
        """Turn the simulated motors on without taking off."""
        self.send_control_command("motoron")

    def turn_motor_off(self):
        """Turn the simulated motors off."""
        self.send_control_command("motoroff")

    def initiate_throw_takeoff(self):
        """Start simulated throw takeoff mode."""
        self.send_control_command("throwfly")

    def takeoff(self):
        """Take off and start race timing when gates are present."""
        if self.is_flying:
            return
        self.LOGGER.info("sending takeoff command to drone")
        self._simulate_latency()
        self._animate_to(z=1.8, speed=max(self.drone["speed"], 100))
        self.is_flying = True
        self._motors_on = True
        self._start_time = self._start_time or time.time()
        self._start_race_timer()

    def land(self, close_window=True):
        """Land the drone and finish race timing."""
        self.LOGGER.info("sending land command to drone")
        self._simulate_latency()
        self._animate_to(z=1.0, speed=max(self.drone["speed"], 100))
        self._finish_race_timer()
        self.is_flying = False
        self._motors_on = False
        if close_window and not self.swarm and self.simulation is not None:
            if self.drone.get("race_gates"):
                self._render_frame(apply_wind=False)
            else:
                self.simulation.quit()

    def streamon(self):
        """Turn on simulated video streaming."""
        self.send_control_command("streamon")
        self.stream_on = True

    def streamoff(self):
        """Turn off simulated video streaming."""
        self.send_control_command("streamoff")
        self.stream_on = False
        if self.background_frame_read is not None:
            self.background_frame_read.stop()
            self.background_frame_read = None

    def emergency(self):
        """Stop the drone immediately."""
        self.send_command_without_return("emergency")
        self.is_flying = False
        self._motors_on = False

    def _require_flying(self):
        if not self.is_flying:
            raise TelloException("Drone is not flying!")

    def _animate_to(self, x=None, y=None, z=None, yaw=None, speed=None):
        current = self.drone["pos"]
        target = [current[0] if x is None else x, current[1] if y is None else y, current[2] if z is None else z]
        speed = speed or self.drone["speed"]
        diff = [target[i] - current[i] for i in range(3)]
        max_diff = max(abs(diff[0]), abs(diff[1]), abs(diff[2]) * 100, 1)
        steps = int(max(max_diff / max(speed, 1) * 60, 1))
        yaw_delta = 0 if yaw is None else (yaw - self.drone["rot"]) / steps
        for _ in range(steps):
            if self.simulation is not None and not self.simulation.running:
                break
            self.drone["pos"][0] += diff[0] / steps
            self.drone["pos"][1] += diff[1] / steps
            self.drone["pos"][2] = max(1.0, self.drone["pos"][2] + diff[2] / steps)
            if yaw is not None:
                self.drone["rot"] += yaw_delta
            self.drone["pitch"] = max(-18, min(18, -diff[1] / max_diff * 12))
            self.drone["roll"] = max(-18, min(18, diff[0] / max_diff * 12))
            self._render_frame()
            time.sleep(0.01)
        self.drone["pitch"] = 0
        self.drone["roll"] = 0
        self._render_frame(apply_wind=False)
        self._update_state()

    def move(self, direction: str, x: int):
        """Move the drone in a named direction by centimetres."""
        self._require_flying()
        self.LOGGER.info("sending move command to drone in direction %s by %s", direction, x)
        self._simulate_latency()
        current_x, current_y, current_z = self.drone["pos"]
        target_x, target_y, target_z = current_x, current_y, current_z
        angle_rad = math.radians(self.drone["rot"])
        if direction == "forward":
            target_x += x * math.sin(angle_rad)
            target_y += x * math.cos(angle_rad)
        elif direction == "back":
            target_x -= x * math.sin(angle_rad)
            target_y -= x * math.cos(angle_rad)
        elif direction == "left":
            target_x += x * math.sin(angle_rad - math.pi / 2)
            target_y += x * math.cos(angle_rad - math.pi / 2)
        elif direction == "right":
            target_x += x * math.sin(angle_rad + math.pi / 2)
            target_y += x * math.cos(angle_rad + math.pi / 2)
        elif direction == "up":
            target_z += x / 100
        elif direction == "down":
            target_z -= x / 100
        else:
            raise TelloException(f"Unknown direction: {direction}")
        self._animate_to(target_x, target_y, target_z)

    def rotate(self, direction: str, x: int):
        """Rotate the drone clockwise or counter-clockwise by degrees."""
        self._require_flying()
        self.LOGGER.info("sending rotate command to drone in direction %s by %s degrees", direction, x)
        self._simulate_latency()
        delta = x if direction == "cw" else -x
        steps = int(max(abs(delta / max(self.drone["speed"], 1) * 60), 1))
        for _ in range(steps):
            if self.simulation is not None and not self.simulation.running:
                break
            self.drone["rot"] += delta / steps
            self._render_frame()
            time.sleep(0.01)
        self._update_state()

    def flip(self, direction: str):
        """Flip the drone in one of the Tello flip directions."""
        self._require_flying()
        if direction not in {"l", "r", "f", "b"}:
            raise TelloException(f"Unknown flip direction: {direction}")
        self.LOGGER.info("sending flip command to drone in direction %s", direction)
        self.drone["flip"] = 24
        self.drone["flip_direction"] = direction
        for _ in range(24):
            if self.simulation is not None and not self.simulation.running:
                break
            self._render_frame(apply_wind=False)
            time.sleep(1 / 60)

    def move_up(self, x: int):
        """Move the drone up by centimetres."""
        self.move("up", x)

    def move_down(self, x: int):
        """Move the drone down by centimetres."""
        self.move("down", x)

    def move_left(self, x: int):
        """Move the drone left by centimetres."""
        self.move("left", x)

    def move_right(self, x: int):
        """Move the drone right by centimetres."""
        self.move("right", x)

    def move_forward(self, x: int):
        """Move the drone forward by centimetres."""
        self.move("forward", x)

    def move_back(self, x: int):
        """Move the drone backward by centimetres."""
        self.move("back", x)

    def move_backward(self, x: int):
        """Move the drone backward by centimetres."""
        self.move_back(x)

    def rotate_clockwise(self, x: int):
        """Rotate the drone clockwise by degrees."""
        self.rotate("cw", x)

    def rotate_counter_clockwise(self, x: int):
        """Rotate the drone counter-clockwise by degrees."""
        self.rotate("ccw", x)

    def flip_left(self):
        """Flip the drone to the left."""
        self.flip("l")

    def flip_right(self):
        """Flip the drone to the right."""
        self.flip("r")

    def flip_forward(self):
        """Flip the drone forward."""
        self.flip("f")

    def flip_back(self):
        """Flip the drone backward."""
        self.flip("b")

    def go_xyz_speed(self, x: int, y: int, z: int, speed: int):
        """Move by relative x, y, z centimetres at the given speed."""
        self._require_flying()
        angle = math.radians(self.drone["rot"])
        dx = y * math.sin(angle) + x * math.sin(angle + math.pi / 2)
        dy = y * math.cos(angle) + x * math.cos(angle + math.pi / 2)
        self._animate_to(self.drone["pos"][0] + dx, self.drone["pos"][1] + dy, self.drone["pos"][2] + z / 100, speed=speed)

    def _go_command(self, parts):
        mid = int(parts[5][1:]) if len(parts) > 5 and parts[5].startswith("m") else None
        if mid is None:
            self.go_xyz_speed(int(parts[1]), int(parts[2]), int(parts[3]), int(parts[4]))
        else:
            self.go_xyz_speed_mid(int(parts[1]), int(parts[2]), int(parts[3]), int(parts[4]), mid)

    def curve_xyz_speed(self, x1: int, y1: int, z1: int, x2: int, y2: int, z2: int, speed: int):
        """Approximate a curved move through two relative points."""
        self.go_xyz_speed(x1, y1, z1, speed)
        self.go_xyz_speed(x2 - x1, y2 - y1, z2 - z1, speed)

    def _curve_command(self, parts):
        mid = int(parts[8][1:]) if len(parts) > 8 and parts[8].startswith("m") else None
        args = [int(v) for v in parts[1:8]]
        if mid is None:
            self.curve_xyz_speed(*args)
        else:
            self.curve_xyz_speed_mid(*args, mid)

    def go_xyz_speed_mid(self, x: int, y: int, z: int, speed: int, mid: int):
        """Mission-pad version of go_xyz_speed kept for compatibility."""
        self.go_xyz_speed(x, y, z, speed)

    def curve_xyz_speed_mid(self, x1: int, y1: int, z1: int, x2: int, y2: int, z2: int, speed: int, mid: int):
        """Mission-pad version of curve_xyz_speed kept for compatibility."""
        self.curve_xyz_speed(x1, y1, z1, x2, y2, z2, speed)

    def go_xyz_speed_yaw_mid(self, x: int, y: int, z: int, speed: int, yaw: int, mid1: int, mid2: int):
        """Simulate the Tello jump command shape."""
        self.go_xyz_speed_mid(x, y, z, speed, mid1)
        self._animate_to(yaw=self.drone["rot"] - yaw, speed=speed)

    def enable_mission_pads(self):
        """Enable simulated mission pad detection."""
        self.send_control_command("mon")

    def disable_mission_pads(self):
        """Disable simulated mission pad detection."""
        self.send_control_command("moff")

    def set_mission_pad_detection_direction(self, x):
        """Set the simulated mission pad detection direction."""
        self.send_control_command(f"mdirection {x}")

    def set_speed(self, x: int):
        """Set the drone speed in centimetres per second."""
        self.drone["speed"] = x
        self.send_control_command(f"speed {x}")

    def send_rc_control(self, left_right_velocity: int, forward_backward_velocity: int, up_down_velocity: int, yaw_velocity: int):
        """Send joystick-style velocity controls to the drone."""
        def clamp100(value):
            return max(-100, min(100, value))

        if time.time() - self.last_rc_control_timestamp > self.TIME_BTW_RC_CONTROL_COMMANDS:
            self.last_rc_control_timestamp = time.time()
            self._apply_rc(clamp100(left_right_velocity), clamp100(forward_backward_velocity), clamp100(up_down_velocity), clamp100(yaw_velocity))

    def _apply_rc(self, left_right_velocity, forward_backward_velocity, up_down_velocity, yaw_velocity):
        if not self.is_flying:
            return
        dt = 0.1
        angle = math.radians(self.drone["rot"])
        self.drone["pos"][0] += (forward_backward_velocity * math.sin(angle) + left_right_velocity * math.sin(angle + math.pi / 2)) * dt
        self.drone["pos"][1] += (forward_backward_velocity * math.cos(angle) + left_right_velocity * math.cos(angle + math.pi / 2)) * dt
        self.drone["pos"][2] = max(1.0, self.drone["pos"][2] + up_down_velocity * dt / 100)
        self.drone["rot"] += yaw_velocity * dt
        self.drone["pitch"] = -forward_backward_velocity / 8
        self.drone["roll"] = left_right_velocity / 8
        self._render_frame()
        self._update_state()

    def set_wifi_credentials(self, ssid: str, password: str):
        """Simulate setting the drone Wi-Fi credentials."""
        self.send_control_command(f"wifi {ssid} {password}")

    def connect_to_wifi(self, ssid: str, password: str):
        """Simulate connecting the drone to a Wi-Fi network."""
        self.send_control_command(f"ap {ssid} {password}")

    def set_network_ports(self, state_packet_port: int, video_stream_port: int):
        """Simulate setting state and video UDP ports."""
        self.send_control_command(f"port {state_packet_port} {video_stream_port}")

    def reboot(self):
        """Simulate rebooting the drone."""
        self.send_command_without_return("reboot")

    def change_vs_udp(self, udp_port):
        """Change the simulated video stream UDP port."""
        self.vs_udp_port = udp_port
        self.send_control_command(f"port 8890 {self.vs_udp_port}")

    def set_video_bitrate(self, bitrate: int):
        """Set simulated video bitrate metadata."""
        self.send_control_command(f"setbitrate {bitrate}")

    def set_video_resolution(self, resolution: str):
        """Set simulated video resolution metadata."""
        self.send_control_command(f"setresolution {resolution}")

    def set_video_fps(self, fps: str):
        """Set simulated video frame-rate metadata."""
        self.send_control_command(f"setfps {fps}")

    def set_video_direction(self, direction: int):
        """Set simulated video camera direction metadata."""
        self.send_control_command(f"downvision {direction}")

    def send_expansion_command(self, expansion_cmd: str):
        """Send a simulated Tello Talent expansion command."""
        self.send_control_command(f"EXT {expansion_cmd}")

    def query_speed(self) -> int:
        """Return the current speed setting."""
        return self.send_read_command_int("speed?")

    def query_battery(self) -> int:
        """Return the simulated battery percentage."""
        return self.send_read_command_int("battery?")

    def query_flight_time(self) -> int:
        """Return the simulated flight time in seconds."""
        return self.send_read_command_int("time?")

    def query_height(self) -> int:
        """Return the simulated height in centimetres."""
        return self.send_read_command_int("height?")

    def query_temperature(self) -> int:
        """Return the simulated temperature."""
        return self.send_read_command_int("temp?")

    def query_attitude(self) -> dict:
        """Return pitch, roll, and yaw values."""
        return Tello.parse_state(self.send_read_command("attitude?"))

    def query_barometer(self) -> int:
        """Return the simulated barometer value."""
        return self.send_read_command_int("baro?") * 100

    def query_distance_tof(self) -> float:
        """Return the simulated time-of-flight distance."""
        tof = self.send_read_command("tof?")
        return int(tof[:-2]) / 10

    def query_wifi_signal_noise_ratio(self) -> str:
        """Return simulated Wi-Fi signal information."""
        return self.send_read_command("wifi?")

    def query_sdk_version(self) -> str:
        """Return the simulated SDK version."""
        return self.send_read_command("sdk?")

    def query_serial_number(self) -> str:
        """Return the simulated serial number."""
        return self.send_read_command("sn?")

    def query_active(self) -> str:
        """Return whether the simulated drone is active."""
        return self.send_read_command("active?")

    def get_udp_video_address(self) -> str:
        """Return the simulated UDP video address."""
        return f"udp://@{self.VS_UDP_IP}:{self.vs_udp_port}"

    def get_frame_read(self, with_queue=False, max_queue_len=32) -> BackgroundFrameRead:
        """Return a simulated BackgroundFrameRead object."""
        if self.background_frame_read is None:
            self.background_frame_read = BackgroundFrameRead(self, with_queue, max_queue_len)
            self.background_frame_read.start()
        return self.background_frame_read

    def get_mission_pad_id(self) -> int:
        """Return the simulated mission pad id."""
        return self.get_state_field("mid")

    def get_mission_pad_distance_x(self) -> int:
        """Return simulated mission pad x distance."""
        return self.get_state_field("x")

    def get_mission_pad_distance_y(self) -> int:
        """Return simulated mission pad y distance."""
        return self.get_state_field("y")

    def get_mission_pad_distance_z(self) -> int:
        """Return simulated mission pad z distance."""
        return self.get_state_field("z")

    def get_pitch(self) -> int:
        """Return the latest pitch value."""
        return self.get_state_field("pitch")

    def get_roll(self) -> int:
        """Return the latest roll value."""
        return self.get_state_field("roll")

    def get_yaw(self) -> int:
        """Return the latest yaw value."""
        return self.get_state_field("yaw")

    def get_speed_x(self) -> int:
        """Return the latest x speed."""
        return self.get_state_field("vgx")

    def get_speed_y(self) -> int:
        """Return the latest y speed."""
        return self.get_state_field("vgy")

    def get_speed_z(self) -> int:
        """Return the latest z speed."""
        return self.get_state_field("vgz")

    def get_acceleration_x(self) -> float:
        """Return the latest x acceleration."""
        return self.get_state_field("agx")

    def get_acceleration_y(self) -> float:
        """Return the latest y acceleration."""
        return self.get_state_field("agy")

    def get_acceleration_z(self) -> float:
        """Return the latest z acceleration."""
        return self.get_state_field("agz")

    def get_lowest_temperature(self) -> int:
        """Return the simulated lowest temperature."""
        return self.get_state_field("templ")

    def get_highest_temperature(self) -> int:
        """Return the simulated highest temperature."""
        return self.get_state_field("temph")

    def get_temperature(self) -> float:
        """Return the average simulated temperature."""
        return (self.get_lowest_temperature() + self.get_highest_temperature()) / 2

    def get_height(self) -> int:
        """Return the simulated height in centimetres."""
        return self.get_state_field("h")

    def get_distance_tof(self) -> int:
        """Return the simulated time-of-flight distance."""
        return self.get_state_field("tof")

    def get_barometer(self) -> int:
        """Return the simulated barometer value."""
        return self.get_state_field("baro") * 100

    def get_flight_time(self) -> int:
        """Return the simulated flight time in seconds."""
        return self.get_state_field("time")

    def get_battery(self) -> int:
        """Return the simulated battery percentage."""
        return self.get_state_field("bat")

    def end(self):
        """Use end in the simulator API."""
        try:
            if self.is_flying:
                self.land(close_window=False)
            if self.stream_on:
                self.streamoff()
        except TelloException:
            pass
        if self.background_frame_read is not None:
            self.background_frame_read.stop()
            self.background_frame_read = None
        if self.simulation is not None:
            self.simulation.unregister(self)

    def __del__(self):
        try:
            self.end()
        except Exception:
            pass


class TelloSwarm:
    """Swarm library for controlling multiple Tellos simultaneously."""

    @staticmethod
    def fromFile(path: str):
        """Create a TelloSwarm from a file of drone addresses."""
        with open(path, "r", encoding="utf-8") as fd:
            ips = fd.readlines()
        return TelloSwarm.fromIps(ips)

    @staticmethod
    def fromIps(ips: list):
        """Create a TelloSwarm from a list of drone addresses."""
        if not ips:
            raise TelloException("No ips provided")
        tellos = [Tello(ip.strip(), swarm=True) for ip in ips]
        for i, tello in enumerate(tellos):
            tello._setSwarmPos(i)
        return TelloSwarm(tellos)

    def __init__(self, tellos: List[Tello]):
        """Create and initialise this object."""
        self.tellos = tellos
        self.barrier = Barrier(len(tellos))
        self.funcBarrier = Barrier(len(tellos) + 1)
        self.funcQueues = [Queue() for _ in tellos]
        self.simulation = tellos[0].simulation if tellos else None

        def worker(i):
            queue = self.funcQueues[i]
            tello = self.tellos[i]
            while True:
                func = queue.get()
                self.funcBarrier.wait()
                func(i, tello)
                self.funcBarrier.wait()

        self.threads = []
        for i, _ in enumerate(tellos):
            thread = Thread(target=worker, daemon=True, args=(i,))
            thread.start()
            self.threads.append(thread)

        if self.simulation is not None:
            self.simulation.render_frame(apply_wind=False)

    def sequential(self, func: Callable[[int, Tello], None]):
        """Run a function on each swarm drone one after another."""
        for i, tello in enumerate(self.tellos):
            func(i, tello)

    def parallel(self, func: Callable[[int, Tello], None]):
        """Run a function on all swarm drones in parallel."""
        for queue in self.funcQueues:
            queue.put(func)
        self.funcBarrier.wait()
        self.funcBarrier.wait()

    def sync(self, timeout: float = None):
        """Wait for swarm threads to reach the same point."""
        return self.barrier.wait(timeout)

    def land(self):
        """Land the drone and finish race timing."""
        for tello in self.tellos:
            tello.land(close_window=False)
        if self.simulation is not None:
            self.simulation.quit()

    def end(self):
        """Use end in the simulator API."""
        for tello in self.tellos:
            tello.end()
        if self.simulation is not None:
            self.simulation.quit()

    def __getattr__(self, attr):
        def callAll(*args, **kwargs):
            self.parallel(lambda i, tello: getattr(tello, attr)(*args, **kwargs))
        return callAll

    def __iter__(self):
        return iter(self.tellos)

    def __len__(self):
        return len(self.tellos)
