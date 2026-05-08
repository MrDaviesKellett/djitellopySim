# DJI Tello Simulator

`djitellopy-sim` lets you write Python code for a DJI Tello-style drone without
needing a real drone. Your program uses familiar `djitellopy` method names, and
the simulator shows a 3D drone in a Pygame window.

This project is useful for lessons, clubs, experiments, and practice. It is
designed so students can learn movement, loops, functions, coordinates, race
gates, and simple drone programming safely on one computer.

## Start Here

- New to Python or drones? Read [QUICKSTART.md](QUICKSTART.md).
- Need to look up every function? Read [API_REFERENCE.md](API_REFERENCE.md).
- Comparing this simulator with the real `djitellopy` library? Read
  [PARITY.md](PARITY.md).

## What You Can Do

- Fly a simulated Tello drone in a 3D window.
- Use commands such as `takeoff()`, `move_forward(100)`, `flip_left()`, and
  `land()`.
- Generate race-gate courses that the drone must fly through in order.
- Show or hide in-view hints for distance, height, and relative gate position.
- Switch between a camera that follows the drone and a zoomed-out course view.
- Time a race from takeoff to landing, including penalties for missed gates or
  gates flown in the wrong order.
- Simulate the Tello Talent expansion LED and 8 by 8 matrix LED screen.
- Run simple swarm programs with more than one simulated drone.

## Installation

Install from PyPI:

```bash
python -m pip install djitellopy-sim
```

Install from this folder while developing the project:

```bash
python -m pip install -e .
```

The package installs its own requirements automatically. It uses `pygame-ce`,
which provides modern prebuilt wheels for Windows, macOS, and Linux. In Python
code it is still imported as `pygame`.

## Your First Flight

Create a file called `first_flight.py`:

```python
from djitellopySim import Tello

tello = Tello()
tello.connect()

tello.takeoff()
tello.move_forward(100)
tello.rotate_clockwise(90)
tello.move_forward(100)
tello.flip_back()
tello.land()
```

Run it:

```bash
python first_flight.py
```

The numbers for movement are centimetres. `move_forward(100)` means move forward
100 cm, which is 1 metre. Rotation numbers are degrees, so
`rotate_clockwise(90)` means turn a quarter turn to the right.

## Race Gates

Race gates are hoops or arches that the drone should fly through in order. A
single command creates a whole course:

```python
from djitellopySim import Tello

tello = Tello()
tello.connect()

tello.setup_race_gates(count=6, course="slalom", seed=7)
tello.set_camera_overview()
tello.set_race_hints(distance=True, height=True, relative=True)

tello.takeoff()
tello.move_forward(250)
tello.land()

print(tello.get_race_time())
```

Course types are:

- `line`
- `slalom`
- `loop`
- `oval`
- `climb`
- `arches`
- `mixed`
- `random`

You can place the drone before a flight:

```python
tello = Tello(start_position=(500, 400, 0))
tello.takeoff(position=(500, 400, 0))
```

The first two numbers are floor coordinates in centimetres. The third number is
height above the floor in centimetres.

You can also place the first gate and let the rest of the course follow from
there:

```python
tello.setup_race_gates(count=6, course="oval", seed=7, first_gate_position=(1000, 800, 180))
```

Race timing starts when the drone takes off and stops when it lands. Missing a
gate adds 10 seconds. Flying through a later gate before the correct next gate
adds 5 seconds.

Students can ask the simulator for measurements before planning a movement:

```python
print(tello.measure_drone_to_gate(1))
print(tello.measure_gate_to_gate(1, 2))
```

These measurements include distance and the angle relative to the current
forward direction, which helps students decide how far to rotate and move.

## Simulator Window Keys

The simulator shows the keymap on screen while it runs.

| Key | What it does |
| --- | --- |
| `F` | Follow the drone with the camera |
| `O` | Show the whole course |
| `+` | Zoom in |
| `-` | Zoom out |
| `D` | Toggle distance hints |
| `H` | Toggle height hints |
| `R` | Toggle relative-position hints |
| `V` | Toggle the drone forward vector |
| `M` | Toggle X/Y/Z measurement overlay |

## Expansion Kit

The simulator can show the Tello Talent expansion light and 8 by 8 matrix LED.

```python
tello.send_expansion_command("led 255 0 0")
tello.send_expansion_command(
    "mled " +
    "00000000"
    "00rrrr00"
    "0rppppr0"
    "0rppppr0"
    "00bbbb00"
    "000bb000"
    "00000000"
    "00000000"
)
```

The top LED uses red, green, and blue values from 0 to 255. The matrix display
is an 8 by 8 grid. Use `0` for black, `r` for red, `b` for blue, and `p` for
purple. There is no green matrix LED.

## Swarms

A swarm is a group of drones controlled together:

```python
from djitellopySim import TelloSwarm

swarm = TelloSwarm.fromFile("ip.txt")
swarm.connect()
swarm.takeoff()
swarm.parallel(lambda i, tello: tello.move_up(50 + i * 20))
swarm.land()
```

The `ip.txt` file should contain one simulated drone address per line.

## Example Files

- `test.py` shows a small single-drone flight.
- `testSwarm.py` and `testSwarm2.py` show swarm flights.
- `raceGatesExample.py` shows race gates, camera modes, and race timing.

## Publishing

This repository is set up as a PyPI project. Build locally with:

```bash
python -m pip install build twine
python -m build
python -m twine check dist/*
```

GitHub Actions publishes to PyPI when a `v*` tag is pushed or a GitHub Release
is published. The workflow is in `.github/workflows/publish.yml`.

### PyPI Trusted Publishing Setup

Use PyPI Trusted Publishing so GitHub Actions can publish without storing a PyPI
password or token in GitHub.

1. Create or log in to your PyPI account at `https://pypi.org`.
2. Open your PyPI account or project publishing settings.
3. Add a GitHub Actions trusted publisher.
4. Use these values:

```text
PyPI project name: djitellopy-sim
Owner: <your GitHub username or organization>
Repository name: <this GitHub repository name>
Workflow name: publish.yml
Environment name: pypi
```

5. In GitHub, open this repository and go to `Settings` -> `Environments`.
6. Create an environment named `pypi`.
7. Optional but recommended: require manual approval for the `pypi` environment.
8. Commit the version you want, push it, then create a GitHub Release or push a
   tag such as `v0.2.6`.

## Important Safety Note

This package is a simulator. It does not fly a real drone. If you later move
your code to a real DJI Tello, test carefully, keep people away from the drone,
and follow your school's or club's safety rules.
