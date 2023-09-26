import pygame
import logging
import threading
from time import sleep
from random import randint, uniform
from math import cos, sin, radians, pi

PI = pi


class TelloException(Exception):
    pass


class Tello:
    # Class variables
    TELLO_IP = "192.168.10.1"  # Tello IP address

    CONTROL_UDP_PORT = 8889
    STATE_UDP_PORT = 8890

    # Set up logger
    HANDLER = logging.StreamHandler()
    FORMATTER = logging.Formatter(
        "[%(levelname)s] %(filename)s - %(lineno)d - %(message)s"
    )
    HANDLER.setFormatter(FORMATTER)

    LOGGER = logging.getLogger("djitellopy simulator")
    LOGGER.addHandler(HANDLER)
    LOGGER.setLevel(logging.DEBUG)

    def __init__(self, host=TELLO_IP):
        self.address = (host, Tello.CONTROL_UDP_PORT)
        self.drone = {}

        # Initialize Pygame
        pygame.init()

        # Set up the display
        self.width = 800
        self.height = 600
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Tello Simulation")

        # Load the sprite image
        self.drone["img"] = pygame.image.load("tello.png")
        self.drone["imgScl"] = 0.08

        # Set the initial position, scale, and rotation
        self.drone["pos"] = [self.width / 2, self.height / 2, 1.0]
        self.drone["rot"] = 0

        # Set the speed of the sprite (in pixels per second)
        self.drone["speed"] = 100

        self.is_flying = False
        self.is_windy = True

        # Create a lock to synchronize access to the attributes
        self.lock = threading.Lock()

        # Create a thread to update the Pygame visual in the background
        self.update_thread = threading.Thread(target=self.update_visual)
        self.update_thread.daemon = True  # Set the thread as a daemon to automatically exit when the main program ends
        self.update_thread.start()

        # message as given by actual Tello class.
        self.LOGGER.info(
            "Tello instance was initialized. Host: '{}'. Port: '{}'.".format(
                host, Tello.CONTROL_UDP_PORT
            )
        )

    def event_loop(self):
        # Handle events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            else:
                pass

    def update_visual(self, windAmt=0.3):
        self.running = True
        clock = pygame.time.Clock()

        noise_x = 0
        noise_y = 0
        noise_z = 0
        noise_t = 0

        while self.running:
            # Update the Pygame visual based on the attributes
            with self.lock:
                self.dt = clock.tick(60) / 1000.0

            # add some random noise to the drone:
            with self.lock:
                if self.is_flying and self.is_windy:
                    self.drone["pos"][0] += noise_x
                    self.drone["pos"][1] += noise_y
                    self.drone["pos"][2] += noise_z * 0.01
                    self.drone["rot"] += noise_t * 0.03

                    if self.drone["pos"][2] < 1:
                        self.drone["pos"][2] = 1

                    noise_x = uniform(-windAmt, windAmt) + noise_x / 2
                    noise_y = uniform(-windAmt, windAmt) + noise_y / 2
                    noise_z = uniform(-windAmt, windAmt) + noise_z / 2
                    noise_t = uniform(-windAmt, windAmt) + noise_t / 2

            with self.lock:
                # Clear the screen
                self.screen.fill((0, 0, 0))

                # Draw the sprite
                scaled_sprite = pygame.transform.scale(
                    self.drone["img"],
                    (
                        int(
                            self.drone["pos"][2]
                            * self.drone["img"].get_width()
                            * self.drone["imgScl"]
                        ),
                        int(
                            self.drone["pos"][2]
                            * self.drone["img"].get_height()
                            * self.drone["imgScl"]
                        ),
                    ),
                )
                rotated_sprite = pygame.transform.rotate(
                    scaled_sprite, self.drone["rot"]
                )
                self.screen.blit(
                    rotated_sprite,
                    (
                        self.drone["pos"][0] - rotated_sprite.get_width() / 2,
                        self.drone["pos"][1] - rotated_sprite.get_height() / 2,
                    ),
                )

                # Update the display
                pygame.display.flip()

            # Delay the next frame
            pygame.time.delay(1000 // 60)

    def connect(self, wait_for_state=True):
        # Connect to the Tello drone (you can simulate this by initializing your Pygame environment)
        if wait_for_state:
            t = randint(1, 20)
            for _ in range(t):
                pygame.time.delay(1000 // 60)
            Tello.LOGGER.debug(
                "'.connect()' received first state packet after {} seconds".format(t)
            )

    def simLat(self, min=0.1, max=3):
        # wait a random amount of time
        waitTime = int(uniform(min, max) * 1000)
        pygame.time.delay(waitTime)

    def takeoff(self):
        Tello.LOGGER.info("sending takoff command to drone")
        self.event_loop()
        self.simLat(max=6)
        # take off drone
        with self.lock:
            current_height = self.drone["pos"][2]

        target_height = 1.5

        height_diff = target_height - current_height
        steps = int(max(abs(height_diff * 100 / self.drone["speed"] * 60), 1))
        delta_height = height_diff / steps
        with self.lock:
            self.is_flying = True
        for _ in range(steps):
            with self.lock:
                self.drone["pos"][2] += delta_height
            pygame.time.delay(1000 // 60)

    def land(self):
        Tello.LOGGER.info("sending land command to drone")
        self.event_loop()
        self.simLat()
        # Land the drone by gradually decreasing its z position to 1.0
        target_height = 1.0
        with self.lock:
            current_height = self.drone["pos"][2]
        height_diff = target_height - current_height
        steps = int(max(abs(height_diff * 100 / self.drone["speed"] * 60), 1))
        delta_height = height_diff / steps
        for _ in range(steps):
            with self.lock:
                self.drone["pos"][2] += delta_height
            pygame.time.delay(1000 // 60)
        with self.lock:
            self.is_flying = False

    def move(self, direction: str, x: int):
        Tello.LOGGER.info(
            f"sending move command to drone in direction {direction} by {x}"
        )
        self.event_loop()
        with self.lock:
            if not self.is_flying:
                raise TelloException("Drone is not flying!")

        self.simLat()

        with self.lock:
            current_x = self.drone["pos"][0]
            current_y = self.drone["pos"][1]
            current_z = self.drone["pos"][2]

        target_x = current_x
        target_y = current_y
        target_z = current_z

        with self.lock:
            angle_rad = radians(self.drone["rot"])

        match direction:
            case "forward":
                target_x = current_x + x * sin(angle_rad)
                target_y = current_y + x * cos(angle_rad)
            case "back":
                target_x = current_x - x * sin(angle_rad)
                target_y = current_y - x * cos(angle_rad)
            case "left":
                with self.lock:
                    angle_rad = radians(self.drone["rot"] + 90)
                target_x = current_x + x * sin(angle_rad)
                target_y = current_y + x * cos(angle_rad)
            case "right":
                with self.lock:
                    angle_rad = radians(self.drone["rot"] + 90)
                target_x = current_x - x * sin(angle_rad)
                target_y = current_y - x * cos(angle_rad)
            case "up":
                x /= 100
                target_z = current_z + x
            case "down":
                x /= 100
                target_z = current_z - x

        diff_x = current_x - target_x
        diff_y = current_y - target_y
        diff_z = target_z - current_z
        maxDiff = max(abs(diff_x), abs(diff_y), abs(diff_z) * 100)
        steps = int(max(maxDiff / self.drone["speed"] * 60, 1))
        delta_x = diff_x / steps
        delta_y = diff_y / steps
        delta_z = diff_z / steps
        for _ in range(steps):
            with self.lock:
                self.drone["pos"][0] += delta_x
                self.drone["pos"][1] += delta_y
                self.drone["pos"][2] += delta_z
            pygame.time.delay(1000 // 60)

    def rotate(self, direction: str, x: int):
        Tello.LOGGER.info(
            f"sending rotate command to drone in direction {direction} by {x} degrees"
        )
        self.event_loop()
        with self.lock:
            if not self.is_flying:
                raise TelloException("Drone is not flying!")

        self.simLat()

        match direction:
            case "cw":
                pass
            case "ccw":
                x = -x

        steps = int(max(abs(x / 90 * 60), 1))
        delta_x = x / steps
        for i in range(steps):
            with self.lock:
                self.drone["rot"] -= delta_x
            pygame.time.delay(1000 // 60)

    def move_forward(self, x):
        # Simulate moving the tello forward by `x` amount.
        self.move("forward", x)

    def move_backward(self, x):
        # Simulate moving the tello backward by `x` amount.
        self.move("back", x)

    def move_left(self, x):
        # Simulate moving the tello left by `x` amount.
        self.move("left", x)

    def move_right(self, x):
        # Simulate moving the tello right by `x` amount.
        self.move("right", x)

    def move_up(self, x):
        # Simulate moving the tello up by `x` amount.
        self.move("up", x)

    def move_down(self, x):
        # Simulate moving the tello down by `x` amount.
        self.move("down", x)

    def rotate_clockwise(self, x):
        # Simulate rotating the tello clockwise by `x` amount.
        self.rotate("cw", x)

    def rotate_counter_clockwise(self, x):
        # Simulate rotating the tello clockwise by `x` amount.
        self.rotate("ccw", x)
