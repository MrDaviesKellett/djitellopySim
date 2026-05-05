import logging
import math
import time
from collections import deque
from queue import Queue
from random import randint, uniform
from threading import Barrier, Lock, Thread
from typing import Callable, Dict, List, Optional, Union

import numpy as np

from physicsSim import sim

PI = math.pi
SIMULATION = None


class TelloException(Exception):
    pass


class BackgroundFrameRead:
    def __init__(self, tello, with_queue=False, maxsize=32):
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
        self.worker.start()

    def update_frame(self):
        while not self.stopped:
            frame = self._make_frame()
            if self.with_queue:
                with self.lock:
                    self.frames.append(frame)
            else:
                self.frame = frame
            time.sleep(1 / 30)

    def get_queued_frame(self):
        with self.lock:
            try:
                return self.frames.popleft()
            except IndexError:
                return None

    @property
    def frame(self):
        if self.with_queue:
            return self.get_queued_frame()
        with self.lock:
            return self._frame

    @frame.setter
    def frame(self, value):
        with self.lock:
            self._frame = value

    def stop(self):
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
        }
        self._state = {}
        self._update_state()

        Tello.LOGGER.info("Tello instance was initialized. Host: '%s'. Port: '%s'.", host, Tello.CONTROL_UDP_PORT)
        if self.simulation is not None:
            self.simulation.register(self)
            self.simulation.event_loop()

    def _setSwarmPos(self, i):
        self.drone["pos"][0] += -260 + 130 * (i % 4)
        self.drone["pos"][1] += -260 + 130 * (i // 4)
        self._last_pos = list(self.drone["pos"])
        self._update_state()

    def _simulate_latency(self, min_delay=0.1, max_delay=0.5):
        if self.is_latency:
            time.sleep(uniform(min_delay, max_delay))

    def simLat(self, min=0.1, max=0.5):
        self._simulate_latency(min, max)

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
        return {"responses": [], "state": self.get_current_state()}

    def get_current_state(self) -> dict:
        return dict(self._update_state())

    def get_state_field(self, key: str):
        state = self.get_current_state()
        if key not in state:
            raise TelloException(f"Could not get state property: {key}")
        return state[key]

    def send_command_with_return(self, command: str, timeout: int = RESPONSE_TIMEOUT) -> str:
        diff = time.time() - self.last_received_command_timestamp
        if diff < self.TIME_BTW_COMMANDS:
            time.sleep(diff)
        self.LOGGER.info("Send command: '%s'", command)
        response = self._handle_command(command, expect_response=True)
        self.last_received_command_timestamp = time.time()
        self.LOGGER.info("Response %s: '%s'", command, response)
        return response

    def send_command_without_return(self, command: str):
        self.LOGGER.info("Send command (no response expected): '%s'", command)
        self._handle_command(command, expect_response=False)

    def send_control_command(self, command: str, timeout: int = RESPONSE_TIMEOUT) -> bool:
        response = "max retries exceeded"
        for _ in range(self.retry_count):
            response = self.send_command_with_return(command, timeout=timeout)
            if "ok" in response.lower():
                return True
        self.raise_result_error(command, response)
        return False

    def send_read_command(self, command: str) -> str:
        response = str(self.send_command_with_return(command))
        if any(word in response for word in ("error", "ERROR", "False")):
            self.raise_result_error(command, response)
        return response

    def send_read_command_int(self, command: str) -> int:
        return int(self.send_read_command(command))

    def send_read_command_float(self, command: str) -> float:
        return float(self.send_read_command(command))

    def raise_result_error(self, command: str, response: str) -> bool:
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
            self.drone["mled"] = " ".join(parts[1:])

    def connect(self, wait_for_state=True):
        self._connected = True
        self.send_control_command("command")
        if wait_for_state:
            time.sleep(randint(1, 5) / 20)
            Tello.LOGGER.debug("'.connect()' received first state packet")

    def send_keepalive(self):
        self.send_control_command("keepalive")

    def turn_motor_on(self):
        self.send_control_command("motoron")

    def turn_motor_off(self):
        self.send_control_command("motoroff")

    def initiate_throw_takeoff(self):
        self.send_control_command("throwfly")

    def takeoff(self):
        if self.is_flying:
            return
        self.LOGGER.info("sending takeoff command to drone")
        self._simulate_latency()
        self._animate_to(z=1.8, speed=max(self.drone["speed"], 100))
        self.is_flying = True
        self._motors_on = True
        self._start_time = self._start_time or time.time()

    def land(self, close_window=True):
        self.LOGGER.info("sending land command to drone")
        self._simulate_latency()
        self._animate_to(z=1.0, speed=max(self.drone["speed"], 100))
        self.is_flying = False
        self._motors_on = False
        if close_window and not self.swarm and self.simulation is not None:
            self.simulation.quit()

    def streamon(self):
        self.send_control_command("streamon")
        self.stream_on = True

    def streamoff(self):
        self.send_control_command("streamoff")
        self.stream_on = False
        if self.background_frame_read is not None:
            self.background_frame_read.stop()
            self.background_frame_read = None

    def emergency(self):
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
            self.drone["pos"][0] += diff[0] / steps
            self.drone["pos"][1] += diff[1] / steps
            self.drone["pos"][2] = max(1.0, self.drone["pos"][2] + diff[2] / steps)
            if yaw is not None:
                self.drone["rot"] += yaw_delta
            self.drone["pitch"] = max(-18, min(18, -diff[1] / max_diff * 12))
            self.drone["roll"] = max(-18, min(18, diff[0] / max_diff * 12))
            time.sleep(0.01)
        self.drone["pitch"] = 0
        self.drone["roll"] = 0
        self._update_state()

    def move(self, direction: str, x: int):
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
        self._require_flying()
        self.LOGGER.info("sending rotate command to drone in direction %s by %s degrees", direction, x)
        self._simulate_latency()
        delta = x if direction == "ccw" else -x
        steps = int(max(abs(delta / max(self.drone["speed"], 1) * 60), 1))
        for _ in range(steps):
            self.drone["rot"] += delta / steps
            time.sleep(0.01)
        self._update_state()

    def flip(self, direction: str):
        self._require_flying()
        if direction not in {"l", "r", "f", "b"}:
            raise TelloException(f"Unknown flip direction: {direction}")
        self.LOGGER.info("sending flip command to drone in direction %s", direction)
        self.drone["flip"] = 24

    def move_up(self, x: int):
        self.move("up", x)

    def move_down(self, x: int):
        self.move("down", x)

    def move_left(self, x: int):
        self.move("left", x)

    def move_right(self, x: int):
        self.move("right", x)

    def move_forward(self, x: int):
        self.move("forward", x)

    def move_back(self, x: int):
        self.move("back", x)

    def move_backward(self, x: int):
        self.move_back(x)

    def rotate_clockwise(self, x: int):
        self.rotate("cw", x)

    def rotate_counter_clockwise(self, x: int):
        self.rotate("ccw", x)

    def flip_left(self):
        self.flip("l")

    def flip_right(self):
        self.flip("r")

    def flip_forward(self):
        self.flip("f")

    def flip_back(self):
        self.flip("b")

    def go_xyz_speed(self, x: int, y: int, z: int, speed: int):
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
        self.go_xyz_speed(x, y, z, speed)

    def curve_xyz_speed_mid(self, x1: int, y1: int, z1: int, x2: int, y2: int, z2: int, speed: int, mid: int):
        self.curve_xyz_speed(x1, y1, z1, x2, y2, z2, speed)

    def go_xyz_speed_yaw_mid(self, x: int, y: int, z: int, speed: int, yaw: int, mid1: int, mid2: int):
        self.go_xyz_speed_mid(x, y, z, speed, mid1)
        self._animate_to(yaw=self.drone["rot"] - yaw, speed=speed)

    def enable_mission_pads(self):
        self.send_control_command("mon")

    def disable_mission_pads(self):
        self.send_control_command("moff")

    def set_mission_pad_detection_direction(self, x):
        self.send_control_command(f"mdirection {x}")

    def set_speed(self, x: int):
        self.drone["speed"] = x
        self.send_control_command(f"speed {x}")

    def send_rc_control(self, left_right_velocity: int, forward_backward_velocity: int, up_down_velocity: int, yaw_velocity: int):
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
        self.drone["rot"] -= yaw_velocity * dt
        self.drone["pitch"] = -forward_backward_velocity / 8
        self.drone["roll"] = left_right_velocity / 8
        self._update_state()

    def set_wifi_credentials(self, ssid: str, password: str):
        self.send_control_command(f"wifi {ssid} {password}")

    def connect_to_wifi(self, ssid: str, password: str):
        self.send_control_command(f"ap {ssid} {password}")

    def set_network_ports(self, state_packet_port: int, video_stream_port: int):
        self.send_control_command(f"port {state_packet_port} {video_stream_port}")

    def reboot(self):
        self.send_command_without_return("reboot")

    def change_vs_udp(self, udp_port):
        self.vs_udp_port = udp_port
        self.send_control_command(f"port 8890 {self.vs_udp_port}")

    def set_video_bitrate(self, bitrate: int):
        self.send_control_command(f"setbitrate {bitrate}")

    def set_video_resolution(self, resolution: str):
        self.send_control_command(f"setresolution {resolution}")

    def set_video_fps(self, fps: str):
        self.send_control_command(f"setfps {fps}")

    def set_video_direction(self, direction: int):
        self.send_control_command(f"downvision {direction}")

    def send_expansion_command(self, expansion_cmd: str):
        self.send_control_command(f"EXT {expansion_cmd}")

    def query_speed(self) -> int:
        return self.send_read_command_int("speed?")

    def query_battery(self) -> int:
        return self.send_read_command_int("battery?")

    def query_flight_time(self) -> int:
        return self.send_read_command_int("time?")

    def query_height(self) -> int:
        return self.send_read_command_int("height?")

    def query_temperature(self) -> int:
        return self.send_read_command_int("temp?")

    def query_attitude(self) -> dict:
        return Tello.parse_state(self.send_read_command("attitude?"))

    def query_barometer(self) -> int:
        return self.send_read_command_int("baro?") * 100

    def query_distance_tof(self) -> float:
        tof = self.send_read_command("tof?")
        return int(tof[:-2]) / 10

    def query_wifi_signal_noise_ratio(self) -> str:
        return self.send_read_command("wifi?")

    def query_sdk_version(self) -> str:
        return self.send_read_command("sdk?")

    def query_serial_number(self) -> str:
        return self.send_read_command("sn?")

    def query_active(self) -> str:
        return self.send_read_command("active?")

    def get_udp_video_address(self) -> str:
        return f"udp://@{self.VS_UDP_IP}:{self.vs_udp_port}"

    def get_frame_read(self, with_queue=False, max_queue_len=32) -> BackgroundFrameRead:
        if self.background_frame_read is None:
            self.background_frame_read = BackgroundFrameRead(self, with_queue, max_queue_len)
            self.background_frame_read.start()
        return self.background_frame_read

    def get_mission_pad_id(self) -> int:
        return self.get_state_field("mid")

    def get_mission_pad_distance_x(self) -> int:
        return self.get_state_field("x")

    def get_mission_pad_distance_y(self) -> int:
        return self.get_state_field("y")

    def get_mission_pad_distance_z(self) -> int:
        return self.get_state_field("z")

    def get_pitch(self) -> int:
        return self.get_state_field("pitch")

    def get_roll(self) -> int:
        return self.get_state_field("roll")

    def get_yaw(self) -> int:
        return self.get_state_field("yaw")

    def get_speed_x(self) -> int:
        return self.get_state_field("vgx")

    def get_speed_y(self) -> int:
        return self.get_state_field("vgy")

    def get_speed_z(self) -> int:
        return self.get_state_field("vgz")

    def get_acceleration_x(self) -> float:
        return self.get_state_field("agx")

    def get_acceleration_y(self) -> float:
        return self.get_state_field("agy")

    def get_acceleration_z(self) -> float:
        return self.get_state_field("agz")

    def get_lowest_temperature(self) -> int:
        return self.get_state_field("templ")

    def get_highest_temperature(self) -> int:
        return self.get_state_field("temph")

    def get_temperature(self) -> float:
        return (self.get_lowest_temperature() + self.get_highest_temperature()) / 2

    def get_height(self) -> int:
        return self.get_state_field("h")

    def get_distance_tof(self) -> int:
        return self.get_state_field("tof")

    def get_barometer(self) -> int:
        return self.get_state_field("baro") * 100

    def get_flight_time(self) -> int:
        return self.get_state_field("time")

    def get_battery(self) -> int:
        return self.get_state_field("bat")

    def end(self):
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
        with open(path, "r", encoding="utf-8") as fd:
            ips = fd.readlines()
        return TelloSwarm.fromIps(ips)

    @staticmethod
    def fromIps(ips: list):
        if not ips:
            raise TelloException("No ips provided")
        tellos = [Tello(ip.strip(), swarm=True) for ip in ips]
        for i, tello in enumerate(tellos):
            tello._setSwarmPos(i)
        return TelloSwarm(tellos)

    def __init__(self, tellos: List[Tello]):
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
            self.simulation.event_loop()

    def sequential(self, func: Callable[[int, Tello], None]):
        for i, tello in enumerate(self.tellos):
            func(i, tello)

    def parallel(self, func: Callable[[int, Tello], None]):
        for queue in self.funcQueues:
            queue.put(func)
        self.funcBarrier.wait()
        self.funcBarrier.wait()

    def sync(self, timeout: float = None):
        return self.barrier.wait(timeout)

    def land(self):
        for tello in self.tellos:
            tello.land(close_window=False)
        if self.simulation is not None:
            self.simulation.quit()

    def end(self):
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
