# Quickstart

This guide is for students who are still learning Python. Follow the steps in
order. Do not worry if you do not understand every line at first.

## 1. Check Python Is Installed

Open a terminal.

On Windows you can use PowerShell. On macOS you can use Terminal.

Type:

```bash
python --version
```

You should see something like:

```text
Python 3.12.3
```

If that does not work, try:

```bash
python3 --version
```

This project needs Python 3.10 or newer.

## 2. Install The Simulator

If the package is on PyPI, install it with:

```bash
python -m pip install djitellopy-sim
```

If you downloaded the project folder from GitHub, open the terminal in this
folder and run:

```bash
python -m pip install -e .
```

The `-e` means "editable". It lets you use the project while also changing the
code.

## 3. Make Your First Python File

Create a new file called `my_first_flight.py`.

Put this code in it:

```python
from djitellopySim import Tello

tello = Tello()
tello.connect()

tello.takeoff()
tello.move_forward(100)
tello.rotate_clockwise(90)
tello.move_forward(100)
tello.land()
```

## 4. Run It

In the terminal, run:

```bash
python my_first_flight.py
```

A window should open and show the drone flying.

## 5. What Each Line Means

```python
from djitellopySim import Tello
```

This gets the `Tello` class from the simulator. A class is like a recipe for
making an object.

```python
tello = Tello()
```

This creates one simulated drone. We store it in a variable called `tello`.

```python
tello.connect()
```

This starts the drone command mode. In the simulator it is instant. With a real
drone this would connect over Wi-Fi.

```python
tello.takeoff()
```

The drone takes off.

```python
tello.move_forward(100)
```

The drone moves forward 100 centimetres. That is 1 metre.

```python
tello.rotate_clockwise(90)
```

The drone turns right by 90 degrees. That is a quarter turn.

```python
tello.land()
```

The drone lands.

## 6. Try Changing The Numbers

Try this:

```python
tello.move_up(50)
tello.move_forward(200)
tello.rotate_counter_clockwise(180)
tello.move_back(100)
```

Useful movement functions:

| Function | Meaning |
| --- | --- |
| `move_up(50)` | Go up 50 cm |
| `move_down(50)` | Go down 50 cm |
| `move_forward(100)` | Go forward 100 cm |
| `move_back(100)` | Go backward 100 cm |
| `move_left(100)` | Go left 100 cm |
| `move_right(100)` | Go right 100 cm |
| `rotate_clockwise(90)` | Turn right 90 degrees |
| `rotate_counter_clockwise(90)` | Turn left 90 degrees |

Always use `takeoff()` before movement and `land()` at the end.

## 7. Try A Flip

```python
from djitellopySim import Tello

tello = Tello()
tello.connect()

tello.takeoff()
tello.flip_forward()
tello.flip_left()
tello.land()
```

The simulator shows the flip direction:

- `flip_forward()` flips end over end forwards.
- `flip_back()` flips end over end backwards.
- `flip_left()` rolls left.
- `flip_right()` rolls right.

## 8. Try Race Gates

Race gates are hoops or arches. The drone should pass through them in number
order.

Create `race_practice.py`:

```python
from djitellopySim import Tello

tello = Tello()
tello.connect()

tello.setup_race_gates(count=5, course="line", seed=3)
tello.set_camera_overview()
tello.set_race_hints(distance=True, height=True, relative=True)

tello.takeoff()
tello.move_forward(250)
tello.move_forward(250)
tello.land()

print(tello.get_race_time())
```

Run it:

```bash
python race_practice.py
```

The `seed` number makes the same random-looking course appear again. Change the
seed to get a different course.

## 9. Race Timing

The race timer starts at `takeoff()` and stops at `land()`.

After landing, use:

```python
print(tello.get_race_time())
```

It gives you a dictionary like this:

```python
{
    "running": False,
    "raw_seconds": 12.4,
    "penalty_seconds": 10,
    "final_seconds": 22.4,
    "missed_gates": 1,
    "wrong_order_gates": 0,
}
```

Penalty rules:

- Missing a gate adds 10 seconds.
- Flying through a later gate before the correct gate adds 5 seconds.

## 10. Camera Controls

From Python:

```python
tello.set_camera_follow(True)
tello.set_camera_overview()
```

In the simulator window:

| Key | What it does |
| --- | --- |
| `F` | Follow the drone |
| `O` | Show the whole course |
| `+` | Zoom in |
| `-` | Zoom out |
| `D` | Show or hide distance hints |
| `H` | Show or hide height hints |
| `R` | Show or hide relative-position hints |

## 11. Expansion LED And Matrix LED

Set the top light:

```python
tello.send_expansion_command("led 255 0 0")
```

That means red = 255, green = 0, blue = 0.

Set the 8 by 8 matrix LED:

```python
heart = (
    "00000000"
    "01100110"
    "11111111"
    "11111111"
    "01111110"
    "00111100"
    "00011000"
    "00000000"
)

tello.send_expansion_command("mled " + heart)
```

The matrix is drawn above the drone. It is an 8 by 8 grid.

## 12. Common Problems

### The window does not open

Check that installation worked:

```bash
python -m pip show djitellopy-sim
```

If you installed from the project folder, try:

```bash
python -m pip install -e .
```

### I get "ModuleNotFoundError"

Python cannot find the simulator package. Install it again, or check that you
are using the same Python in your terminal and editor.

### The drone does not move

Make sure your code has:

```python
tello.takeoff()
```

before movement commands.

### My movement is too small or too big

Movement uses centimetres:

- 10 cm is small.
- 100 cm is 1 metre.
- 500 cm is 5 metres.

### The program keeps running

Use:

```python
tello.land()
tello.end()
```

`land()` lands the drone. `end()` closes simulator resources.
