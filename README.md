# DJI Tello Simulator

`djitellopy-sim` is a local simulator for DJI Tello programs. It exposes a
`djitellopy`-style `Tello` and `TelloSwarm` API while rendering drones in a
Pygame 3D scene instead of sending UDP commands to physical hardware.

## Features

- 3D projected drone renderer with altitude, yaw, tilt, rotors, shadows, trails,
  and extension LED color.
- Random flyable race-gate courses with ordered pass-through tracking and a
  visual measurement HUD for the next gate.
- Single-drone and swarm simulation.
- Broad compatibility with `djitellopy` 2.5.0 method names.
- Simulated state packets, query commands, RC control, video frame reads, mission
  pad toggles, video settings, and Tello Talent extension commands.
- PyPI-ready packaging with automatic dependency installation.
- Uses `pygame-ce` for modern prebuilt wheels, including macOS universal2
  wheels, while still importing the runtime module as `pygame`.

## Installation

From a local checkout:

```bash
python -m pip install .
```

For development:

```bash
python -m pip install -e .
```

## Usage

```python
from djitellopySim import Tello

tello = Tello()
tello.connect()
tello.takeoff()
tello.move_forward(100)
tello.rotate_clockwise(90)
tello.send_expansion_command("led 0 255 255")
tello.flip_back()
tello.land()
```

Race gates can be generated with one simulator command. Courses can use
`line`, `slalom`, `loop`, `climb`, `arches`, `mixed`, or `random` layouts.
The 3D view shows ordered gates with the active gate highlighted. Hints are
drawn next to the active gate and can be toggled individually:

```python
from djitellopySim import Tello

tello = Tello()
tello.connect()
tello.send_control_command("racegates 5 slalom")
tello.send_control_command("camerafollow on")
tello.send_control_command("racehints distance on")
tello.send_control_command("racehints height on")
tello.takeoff()

print(tello.get_race_gate_measurements())
```

Camera and hint controls are available from code or from the simulator window:

```python
tello.send_control_command("cameraoverview")
tello.send_control_command("camerafollow on")
tello.send_control_command("racehints relative on")
```

Keyboard shortcuts are shown in the top-right of the simulator. `F` follows the
drone, `O` shows the whole course, `+`/`-` zoom, and `D`, `H`, `R` toggle
distance, height, and relative-position hints.

Swarm code follows the same shape as `djitellopy`:

```python
from djitellopySim import TelloSwarm

swarm = TelloSwarm.fromFile("ip.txt")
swarm.connect()
swarm.takeoff()
swarm.parallel(lambda i, tello: tello.move_up(50 + i * 10))
swarm.land()
```

## Publishing

Update the package metadata in `pyproject.toml`, then build locally:

```bash
python -m pip install build
python -m build
```

This repository includes `.github/workflows/publish.yml`, which publishes to
PyPI automatically when a `v*` tag is pushed or a GitHub Release is published.

### PyPI Trusted Publishing Setup

Use PyPI Trusted Publishing so GitHub Actions can publish without a stored PyPI
token.

1. Create or log in to your PyPI account at `https://pypi.org`.
2. If `djitellopy-sim` already exists on PyPI and you own it, open the project,
   go to `Manage project` -> `Publishing`, then add a GitHub Actions trusted
   publisher.
3. If this will be the first upload for `djitellopy-sim`, open your account
   `Publishing` page and add a pending GitHub Actions publisher for the new
   project name.
4. Enter these publisher values:

```text
PyPI project name: djitellopy-sim
Owner: <your GitHub username or organization>
Repository name: <this GitHub repository name>
Workflow name: publish.yml
Environment name: pypi
```

5. In this GitHub repository, create an environment named `pypi` under
   `Settings` -> `Environments`. Optional but recommended: require manual
   approval for deployments to that environment.
6. Make sure `pyproject.toml` has the version you want to publish, commit the
   changes, push them to GitHub, then create and publish a GitHub Release.

## API Parity

The simulator targets `djitellopy` 2.5.0. See `PARITY.md` for the implemented
surface and the known differences from real hardware behavior.
