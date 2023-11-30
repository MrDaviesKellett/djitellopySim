import logging
import time
from random import randint, uniform
from math import cos, sin, radians, pi
from threading import Thread, Barrier
from queue import Queue
from typing import List, Callable
from physicsSim import sim

PI = pi

SIMULATION = sim()

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

    def __init__(self, host=TELLO_IP, swarm = False):
        self.flightPathTaken = []
        self.address = (host, Tello.CONTROL_UDP_PORT)
        self.drone = {}

        self.simulation = SIMULATION

        self.drone["scl"] = 0.08

        # Set the initial position, scale, and rotation
        self.drone["pos"] = [self.simulation.width / 2, self.simulation.height / 2, 1.0]
        self.drone["rot"] = 0

        # Set the speed of the sprite (in pixels per second)
        self.drone["speed"] = 400
        self.drone["flip"] = 0
        self.drone["led"] = (0, 0, 0)
        self.swarm = swarm

        self.is_flying = False
        self.is_windy = True
        self.is_latency = True

        # message as given by actual Tello class.
        self.LOGGER.info(
            "Tello instance was initialized. Host: '{}'. Port: '{}'.".format(
                host, Tello.CONTROL_UDP_PORT
            )
        )
        self.simulation.register(self)
        if swarm is False:
            self.simulation.event_loop()

    def _setSwarmPos(self, i):
        self.drone["pos"][0] += - 260 + 130 * (i % 4)
        self.drone["pos"][1] += - 260 + 130 * (i // 4)


    def connect(self, wait_for_state=True):
        # Connect to the Tello drone
        if wait_for_state:
            t = randint(1, 5) / 5
            time.sleep(t)
            Tello.LOGGER.debug(
                "'.connect()' received first state packet after {} seconds".format(t)
            )

    def simLat(self, min=0.1, max=0.5):
        # wait a random amount of time
        if self.is_latency == False:
            return False
        waitTime = uniform(min, max)
        time.sleep(waitTime)

    def takeoff(self):
        Tello.LOGGER.info("sending takoff command to drone")
        self.simLat()
        current_height = self.drone["pos"][2]

        target_height = 1.5

        height_diff = target_height - current_height
        steps = int(max(abs(height_diff * 100 / self.drone["speed"] * 60), 1))
        delta_height = height_diff / steps
        self.is_flying = True
        
        for _ in range(steps):
            self.drone["pos"][2] += delta_height
            time.sleep(0.01)

    def land(self):
        Tello.LOGGER.info("sending land command to drone")
        self.simLat()
        # Land the drone by gradually decreasing its z position to 1.0
        target_height = 1.0
        current_height = self.drone["pos"][2]
        height_diff = target_height - current_height
        steps = int(max(abs(height_diff * 100 / self.drone["speed"] * 60), 1))
        delta_height = height_diff / steps
        for _ in range(steps):
            self.drone["pos"][2] += delta_height
            time.sleep(0.01)
        self.is_flying = False
        if self.swarm is False:
            self.simulation.quit()

    def move(self, direction: str, x: int):
        Tello.LOGGER.info(
            f"sending move command to drone in direction {direction} by {x}"
        )
        if not self.is_flying:
            raise TelloException("Drone is not flying!")

        self.simLat()

        current_x = self.drone["pos"][0]
        current_y = self.drone["pos"][1]
        current_z = self.drone["pos"][2]

        target_x = current_x
        target_y = current_y
        target_z = current_z

        angle_rad = radians(self.drone["rot"])

        match direction:
            case "forward":
                target_x = current_x + x * sin(angle_rad)
                target_y = current_y + x * cos(angle_rad)
            case "back":
                target_x = current_x - x * sin(angle_rad)
                target_y = current_y - x * cos(angle_rad)
            case "left":
                angle_rad = radians(self.drone["rot"] - 90)
                target_x = current_x + x * sin(angle_rad)
                target_y = current_y + x * cos(angle_rad)
            case "right":
                angle_rad = radians(self.drone["rot"] + 90)
                target_x = current_x + x * sin(angle_rad)
                target_y = current_y + x * cos(angle_rad)
            case "up":
                x /= 100
                target_z = current_z + x
            case "down":
                x /= 100
                target_z = current_z - x

        diff_x = target_x - current_x
        diff_y = target_y - current_y
        diff_z = target_z - current_z
        maxDiff = max(abs(diff_x), abs(diff_y), abs(diff_z) * 100)
        steps = int(max(maxDiff / self.drone["speed"] * 60, 1))
        delta_x = diff_x / steps
        delta_y = diff_y / steps
        delta_z = diff_z / steps
        for _ in range(steps):
            self.drone["pos"][0] += delta_x
            self.drone["pos"][1] += delta_y
            self.drone["pos"][2] += delta_z
            time.sleep(0.01)

    def rotate(self, direction: str, x: int):
        Tello.LOGGER.info(
            f"sending rotate command to drone in direction {direction} by {x} degrees"
        )
        
        if not self.is_flying:
            raise TelloException("Drone is not flying!")

        self.simLat()

        match direction:
            case "cw":
                pass
            case "ccw":
                x = -x

        steps = int(max(abs(x / self.drone["speed"] * 60), 1))
        delta_x = x / steps
        for i in range(steps):
            self.drone["rot"] -= delta_x
            time.sleep(0.01)

    def flip(self, direction: str):
        Tello.LOGGER.info(
            f"sending flip command to drone in direction {direction}"
        )
        self.drone["flip"] = 24

    def flip_left(self):
        self.flip("l")

    def flip_right(self):
        self.flip("r")
    
    def flip_forward(self):
        self.flip("f")

    def flip_back(self):
        self.flip("b")

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

    def send_command_without_return(self, cmd):
        c = cmd.split()
        if c[0] == "EXT" and c[1] == "led":
            self.drone["led"] = (int(c[2]), int(c[3]), int(c[4]))
        else:
            pass

class TelloSwarm:
    """Swarm library for controlling multiple Tellos simultaneously
    """

    @staticmethod
    def fromFile(path: str):
        """Create TelloSwarm from file. The file should contain one IP address per line.

        Arguments:
            path: path to the file
        """
        with open(path, 'r') as fd:
            ips = fd.readlines()

        return TelloSwarm.fromIps(ips)

    @staticmethod
    def fromIps(ips: list):
        """Create TelloSwarm from a list of IP addresses.

        Arguments:
            ips: list of IP Addresses
        """
        if not ips:
            raise TelloException("No ips provided")

        tellos = []
        for ip in ips:
            tellos.append(Tello(ip.strip(), swarm = True))

        for i in range(len(tellos)):
            tellos[i]._setSwarmPos(i)

        

        return TelloSwarm(tellos)

    def __init__(self, tellos: List[Tello]):
        """Initialize a TelloSwarm instance

        Arguments:
            tellos: list of [Tello][tello] instances
        """
        self.tellos = tellos
        self.barrier = Barrier(len(tellos))
        self.funcBarrier = Barrier(len(tellos) + 1)
        self.funcQueues = [Queue() for tello in tellos]
        self.simulation = SIMULATION

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

        self.simulation.event_loop()

    def sequential(self, func: Callable[[int, Tello], None]):
        """Call `func` for each tello sequentially. The function retrieves
        two arguments: The index `i` of the current drone and `tello` the
        current [Tello][tello] instance.

        ```python
        swarm.parallel(lambda i, tello: tello.land())
        ```
        """

        for i, tello in enumerate(self.tellos):
            func(i, tello)

    def parallel(self, func: Callable[[int, Tello], None]):
        """Call `func` for each tello in parallel. The function retrieves
        two arguments: The index `i` of the current drone and `tello` the
        current [Tello][tello] instance.

        You can use `swarm.sync()` for syncing between threads.

        ```python
        swarm.parallel(lambda i, tello: tello.move_up(50 + i * 10))
        ```
        """

        for queue in self.funcQueues:
            queue.put(func)

        self.funcBarrier.wait()
        self.funcBarrier.wait()

    def sync(self, timeout: float = None):
        """Sync parallel tello threads. The code continues when all threads
        have called `swarm.sync`.

        ```python
        def doStuff(i, tello):
            tello.move_up(50 + i * 10)
            swarm.sync()

            if i == 2:
                tello.flip_back()
            # make all other drones wait for one to complete its flip
            swarm.sync()

        swarm.parallel(doStuff)
        ```
        """
        return self.barrier.wait(timeout)

    def land(self):
        for t in self.tellos:
            t.land()
        self.simulation.quit()

    def __getattr__(self, attr):
        """Call a standard tello function in parallel on all tellos.

        ```python
        swarm.command()
        swarm.takeoff()
        swarm.move_up(50)
        ```
        """
        def callAll(*args, **kwargs):
            self.parallel(lambda i, tello: getattr(tello, attr)(*args, **kwargs))

        return callAll

    def __iter__(self):
        """Iterate over all drones in the swarm.

        ```python
        for tello in swarm:
            print(tello.get_battery())
        ```
        """
        return iter(self.tellos)

    def __len__(self):
        """Return the amount of tellos in the swarm

        ```python
        print("Tello count: {}".format(len(swarm)))
        ```
        """
        return len(self.tellos)
