# API Reference

This page lists the public functions students are expected to use.

Most function names match the real `djitellopy` library. The simulator tries to
make the same code shape work locally, but it does not connect to a real drone.

## Quick Rules

- Movement distances use centimetres.
- Rotation uses degrees.
- Speeds usually use centimetres per second.
- Use `connect()` before flying.
- Use `takeoff()` before movement.
- Use `land()` when your flight is finished.
- Functions that say "simulator only" are helpful in this project but are not
  part of the real drone library.

## Importing

```python
from djitellopySim import Tello, TelloSwarm, TelloException
```

## Tello

`Tello` is the main class. One `Tello` object means one simulated drone.

```python
tello = Tello()
```

### `Tello(host=TELLO_IP, retry_count=RETRY_COUNT, vs_udp=VS_UDP_PORT, swarm=False, start_visual=True, start_position=None)`

Creates a simulated drone.

- `host` is the drone address. In the simulator it is mostly used to identify
  drones.
- `retry_count` is kept for compatibility with `djitellopy`.
- `vs_udp` is the video stream UDP port setting.
- `swarm=True` tells the simulator this drone is part of a swarm.
- `start_visual=False` creates the drone without opening the visual window.
- `start_position=(x, y, z)` places the drone before the flight starts. `x` and
  `y` are floor coordinates in centimetres. `z` is height above the floor in
  centimetres.

Example:

```python
tello = Tello()
tello_at_start = Tello(start_position=(500, 400, 0))
```

### `set_position(x=None, y=None, z=None, position=None)`

Places the drone before it starts flying.

```python
tello.set_position(500, 400, 0)
tello.set_position(position=(500, 400, 0))
```

Use this before `takeoff()`. The simulator raises an error if you try to place
the drone while it is already flying.

## Connection And Lifecycle

### `connect(wait_for_state=True)`

Connects to the simulated drone.

```python
tello.connect()
```

### `end()`

Stops streams, closes the simulator window resources, and cleans up the drone.

```python
tello.end()
```

### `reboot()`

Simulates a reboot command. It returns `True` when the command is accepted.

### `emergency()`

Stops flying immediately. Use this if a program has gone wrong.

```python
tello.emergency()
```

### `send_keepalive()`

Sends a keepalive command. In the simulator this is accepted without real
network activity.

### `turn_motor_on()`

Turns the simulated motors on without taking off.

### `turn_motor_off()`

Turns the simulated motors off.

### `initiate_throw_takeoff()`

Simulates throw takeoff mode.

## Basic Flight

### `takeoff(x=None, y=None, z=None, position=None)`

Makes the drone take off. Race timing starts here.

```python
tello.takeoff()
tello.takeoff(position=(500, 400, 0))
```

### `land(close_window=True)`

Makes the drone land. Race timing stops here.

- `close_window=True` also closes the simulator window.
- `close_window=False` keeps the simulator window open.

```python
tello.land()
```

### `move(direction, x)`

Moves in one direction.

- `direction` can be `"up"`, `"down"`, `"left"`, `"right"`, `"forward"`, or
  `"back"`.
- `x` is centimetres.

```python
tello.move("forward", 100)
```

### `move_up(x)`

Moves up `x` centimetres.

### `move_down(x)`

Moves down `x` centimetres.

### `move_left(x)`

Moves left `x` centimetres.

### `move_right(x)`

Moves right `x` centimetres.

### `move_forward(x)`

Moves forward `x` centimetres.

### `move_back(x)`

Moves backward `x` centimetres.

### `move_backward(x)`

Same as `move_back(x)`.

Example:

```python
tello.move_up(50)
tello.move_forward(100)
tello.move_back(100)
```

## Rotation And Flips

### `rotate(direction, x)`

Rotates the drone.

- `direction` can be `"cw"` for clockwise or `"ccw"` for counter-clockwise.
- `x` is degrees.

```python
tello.rotate("cw", 90)
```

### `rotate_clockwise(x)`

Turns right by `x` degrees.

### `rotate_counter_clockwise(x)`

Turns left by `x` degrees.

### `flip(direction)`

Flips the drone.

- `direction` can be `"l"`, `"r"`, `"f"`, or `"b"`.

```python
tello.flip("f")
```

### `flip_left()`

Rolls left.

### `flip_right()`

Rolls right.

### `flip_forward()`

Flips end over end forwards.

### `flip_back()`

Flips end over end backwards.

## Advanced Movement

These commands match the shape of real Tello SDK commands. They are useful for
students who are ready for coordinates.

### `go_xyz_speed(x, y, z, speed)`

Moves to a position relative to the current drone.

- `x` is left/right centimetres.
- `y` is forward/back centimetres.
- `z` is up/down centimetres.
- `speed` is centimetres per second.

```python
tello.go_xyz_speed(0, 200, 50, 50)
```

### `curve_xyz_speed(x1, y1, z1, x2, y2, z2, speed)`

Moves along an approximated curve through two relative points.

```python
tello.curve_xyz_speed(100, 100, 0, 200, 200, 50, 40)
```

### `go_xyz_speed_mid(x, y, z, speed, mid)`

Mission-pad version of `go_xyz_speed`. The simulator treats it as a normal
relative movement and keeps the method for compatibility.

### `curve_xyz_speed_mid(x1, y1, z1, x2, y2, z2, speed, mid)`

Mission-pad version of `curve_xyz_speed`. The simulator approximates it.

### `go_xyz_speed_yaw_mid(x, y, z, speed, yaw, mid1, mid2)`

Simulates the Tello `jump` command shape.

## RC Control

### `send_rc_control(left_right_velocity, forward_backward_velocity, up_down_velocity, yaw_velocity)`

Sends joystick-style control values.

- Positive left/right moves left.
- Positive forward/back moves forward.
- Positive up/down moves up.
- Positive yaw turns clockwise.

```python
tello.send_rc_control(0, 40, 0, 0)
```

## Race Gates

Race gate functions are simulator only.

### `setup_race_gates(count=5, course="line", seed=None, min_randomness=0, max_randomness=35, first_gate_position=None)`

Creates a race course.

- `count` is the number of gates.
- `course` can be `"line"`, `"slalom"`, `"loop"`, `"climb"`, `"arches"`,
  `"mixed"`, `"oval"`, or `"random"`.
- `seed` makes a random course repeatable.
- `min_randomness` and `max_randomness` control how much each gate is shifted
  from the course template.
- `first_gate_position=(x, y, z)` places the first gate. `x` and `y` are floor
  coordinates in centimetres. `z` is gate height in centimetres.

```python
tello.setup_race_gates(count=6, course="loop", seed=12, max_randomness=20)
tello.setup_race_gates(count=6, course="oval", seed=12, first_gate_position=(1000, 800, 180))
```

### `clear_race_gates()`

Removes all race gates and clears race progress.

### `get_race_gates()`

Returns a list of dictionaries describing the gates.

Each gate includes information such as its number, position, height, radius,
rotation, type, and whether it has been passed.

### `get_next_race_gate()`

Returns the next gate the drone should fly through, or `None` if there is no
next gate.

### `get_race_gate_measurements()`

Returns measurements for the next gate. This is useful for printing help for a
student or making a custom display.

Example result:

```python
{
    "gate": 2,
    "distance_cm": 345,
    "flat_distance_cm": 334,
    "angle_from_drone_forward_degrees": 15,
    "relative_x_cm": 120,
    "relative_y_cm": 320,
    "relative_z_cm": 80,
}
```

### `measure_drone_to_gate(gate_id=None)`

Measures from the drone to a race gate. If `gate_id` is not given, it measures
to the next gate.

The result includes distance, flat ground distance, relative x/y/z movement, and
the angle from the drone's forward direction. Students can use this to plan a
turn and then a `move_forward()` distance.

### `measure_gate_to_gate(from_gate_id, to_gate_id=None)`

Measures from one gate to another. If `to_gate_id` is not given, it measures to
the next numbered gate.

The result includes distance and the angle from the first gate's forward
direction to the second gate.

### `set_race_hints(distance=None, height=None, relative=None, forward=None, measure=None)`

Turns race-gate hints on or off in the simulator view.

```python
tello.set_race_hints(distance=True, height=True, relative=False, forward=True, measure=True)
```

### `get_race_time()`

Returns race timing information.

```python
print(tello.get_race_time())
```

The result contains:

- `running`: whether the timer is still running.
- `elapsed_seconds`: time from takeoff to landing before penalties.
- `penalty_seconds`: added penalty time.
- `final_seconds`: raw time plus penalties.
- `missed_gates`: number of gates not completed.
- `wrong_order_gates`: number of wrong-order gate crossings.

Penalty rules:

- Missed gate: +10 seconds.
- Wrong-order gate: +5 seconds.

## Camera And View

Camera functions are simulator only.

### `set_camera_follow(enabled=True)`

Makes the camera follow the drone.

```python
tello.set_camera_follow(True)
```

### `set_camera_overview()`

Zooms out so the course and drone are easier to see.

```python
tello.set_camera_overview()
```

## Video And Frames

The simulator does not stream real drone video. It returns generated placeholder
frames so code that expects the video API can still run.

### `streamon()`

Turns the simulated video stream on.

### `streamoff()`

Turns the simulated video stream off.

### `get_udp_video_address()`

Returns the simulated UDP video address.

### `get_frame_read(with_queue=False, max_queue_len=32)`

Returns a `BackgroundFrameRead` object.

```python
frame_reader = tello.get_frame_read()
frame = frame_reader.frame
```

### `set_video_bitrate(bitrate)`

Sets simulated video bitrate metadata.

### `set_video_resolution(resolution)`

Sets simulated video resolution metadata.

### `set_video_fps(fps)`

Sets simulated video frames per second metadata.

### `set_video_direction(direction)`

Sets simulated camera direction metadata.

## Mission Pads

Mission pad functions are kept for compatibility. The simulator uses synthetic
mission pad values.

### `enable_mission_pads()`

Turns mission pad mode on.

### `disable_mission_pads()`

Turns mission pad mode off.

### `set_mission_pad_detection_direction(x)`

Sets mission pad detection direction.

Common values:

- `0`: downward camera
- `1`: forward camera
- `2`: both cameras

### `get_mission_pad_id()`

Returns the current simulated mission pad id.

### `get_mission_pad_distance_x()`

Returns simulated x distance from a mission pad.

### `get_mission_pad_distance_y()`

Returns simulated y distance from a mission pad.

### `get_mission_pad_distance_z()`

Returns simulated z distance from a mission pad.

## Speed, Wi-Fi, And Settings

### `set_speed(x)`

Sets the drone speed in centimetres per second.

```python
tello.set_speed(50)
```

### `query_speed()`

Returns the current speed setting.

### `set_wifi_credentials(ssid, password)`

Simulates setting Wi-Fi credentials.

### `connect_to_wifi(ssid, password)`

Simulates connecting the drone to Wi-Fi.

### `set_network_ports(state_packet_port, video_stream_port)`

Simulates setting the drone network ports.

### `change_vs_udp(udp_port)`

Changes the simulated video stream UDP port.

## Expansion Kit

### `send_expansion_command(expansion_cmd)`

Sends a Tello Talent expansion command.

Set the top LED:

```python
tello.send_expansion_command("led 255 0 0")
```

Set the 8 by 8 matrix LED:

```python
pattern = (
    "00000000"
    "00rrrr00"
    "0rppppr0"
    "0rppppr0"
    "00bbbb00"
    "000bb000"
    "00000000"
    "00000000"
)

tello.send_expansion_command("mled " + pattern)
```

The matrix is shown above the drone. Use `0` for black, `r` for red, `b` for
blue, and `p` for purple. There is no green matrix LED.

## State Queries

Query methods ask the drone for a value right now.

### `query_battery()`

Returns battery percentage.

### `query_flight_time()`

Returns flight time in seconds.

### `query_height()`

Returns height in centimetres.

### `query_temperature()`

Returns temperature.

### `query_attitude()`

Returns pitch, roll, and yaw as a dictionary.

### `query_barometer()`

Returns barometer height.

### `query_distance_tof()`

Returns time-of-flight distance.

### `query_wifi_signal_noise_ratio()`

Returns simulated Wi-Fi signal-to-noise value.

### `query_sdk_version()`

Returns simulated SDK version.

### `query_serial_number()`

Returns simulated serial number.

### `query_active()`

Returns whether the simulator thinks the drone is active.

## State Getters

Getter methods read the latest stored state.

### `get_current_state()`

Returns the full state dictionary.

### `get_state_field(key)`

Returns one value from the state dictionary.

```python
height = tello.get_state_field("h")
```

### `get_pitch()`

Returns pitch.

### `get_roll()`

Returns roll.

### `get_yaw()`

Returns yaw.

### `get_speed_x()`

Returns x speed.

### `get_speed_y()`

Returns y speed.

### `get_speed_z()`

Returns z speed.

### `get_acceleration_x()`

Returns x acceleration.

### `get_acceleration_y()`

Returns y acceleration.

### `get_acceleration_z()`

Returns z acceleration.

### `get_lowest_temperature()`

Returns the lower simulated temperature value.

### `get_highest_temperature()`

Returns the higher simulated temperature value.

### `get_temperature()`

Returns the average simulated temperature.

### `get_height()`

Returns height in centimetres.

### `get_distance_tof()`

Returns time-of-flight distance.

### `get_barometer()`

Returns barometer height.

### `get_flight_time()`

Returns flight time in seconds.

### `get_battery()`

Returns battery percentage.

## Command Helpers

Most students should use the friendly methods above. These helpers are useful
when you want to send Tello SDK command strings directly.

### `send_command_with_return(command, timeout=RESPONSE_TIMEOUT)`

Sends a command string and returns the response text.

```python
response = tello.send_command_with_return("battery?")
```

### `send_command_without_return(command)`

Sends a command string without waiting for a response.

### `send_control_command(command, timeout=RESPONSE_TIMEOUT)`

Sends a command that should return `ok`. It returns `True` when accepted.

```python
tello.send_control_command("forward 100")
```

### `send_read_command(command)`

Sends a read command and returns text.

### `send_read_command_int(command)`

Sends a read command and converts the answer to an integer.

### `send_read_command_float(command)`

Sends a read command and converts the answer to a float.

### `raise_result_error(command, response)`

Raises a `TelloException` when a command response is not `ok`.

### `parse_state(state)`

Converts a Tello state string into a dictionary.

```python
state = Tello.parse_state("pitch:0;roll:0;yaw:90;bat:100;")
```

### `get_own_udp_object()`

Compatibility helper. The simulator returns `None`.

### `simLat(min=0.1, max=0.5)`

Simulator-only helper that adds a random delay. This can make commands feel more
like a real drone connection.

## Direct Command Strings

You can use direct strings with `send_control_command()`.

Common real Tello-style commands:

```python
tello.send_control_command("takeoff")
tello.send_control_command("takeoff 500 400 0")
tello.send_control_command("forward 100")
tello.send_control_command("cw 90")
tello.send_control_command("flip l")
tello.send_control_command("land")
```

Simulator-only commands:

```python
tello.send_control_command("racegates 5 slalom")
tello.send_control_command("racegates 6 loop 12")
tello.send_control_command("racegates 6 oval 12 0 20 1000 800 180")
tello.send_control_command("cleargates")
tello.send_control_command("racehints distance on")
tello.send_control_command("racehints height off")
tello.send_control_command("racehints relative on")
tello.send_control_command("racehints forward on")
tello.send_control_command("racehints measure on")
tello.send_control_command("racehints off")
tello.send_control_command("camerafollow on")
tello.send_control_command("cameraoverview")
```

Expansion commands:

```python
tello.send_control_command("EXT led 255 0 0")
tello.send_control_command("EXT mled 0000000000rrrr000rppppr00rppppr000bbbb00000bb000000000000000000")
```

Read commands:

```python
tello.send_read_command("battery?")
tello.send_read_command("height?")
tello.send_read_command("time?")
```

## BackgroundFrameRead

`BackgroundFrameRead` is returned by `get_frame_read()`.

### `start()`

Starts frame reading and returns the same reader object.

### `frame`

Property that returns the latest frame.

```python
reader = tello.get_frame_read()
latest_frame = reader.frame
```

### `get_queued_frame()`

Returns the next queued frame when queue mode is enabled.

### `update_frame()`

Updates the stored frame. Most students do not need to call this directly.

### `stop()`

Stops frame reading.

## TelloSwarm

`TelloSwarm` controls multiple simulated drones.

### `TelloSwarm.fromFile(path)`

Creates a swarm from a text file of addresses.

```python
swarm = TelloSwarm.fromFile("ip.txt")
```

### `TelloSwarm.fromIps(ips)`

Creates a swarm from a Python list.

```python
swarm = TelloSwarm.fromIps(["192.168.10.1", "192.168.10.2"])
```

### `TelloSwarm(tellos)`

Creates a swarm from a list of `Tello` objects.

### `sequential(func)`

Runs a function once for each drone, one after another.

```python
swarm.sequential(lambda i, tello: tello.move_up(50))
```

### `parallel(func)`

Runs a function for all drones at the same time.

```python
swarm.parallel(lambda i, tello: tello.move_forward(100))
```

### `sync(timeout=None)`

Waits at a barrier so parallel swarm actions can stay together.

### `land()`

Lands every drone in the swarm.

### `end()`

Ends every drone in the swarm.

### `len(swarm)`

Returns the number of drones.

```python
print(len(swarm))
```

### `for tello in swarm`

Loops through the drones.

```python
for tello in swarm:
    print(tello.get_battery())
```

### Broadcast methods

If you call a normal `Tello` method on a swarm, the swarm sends it to every
drone.

```python
swarm.connect()
swarm.takeoff()
swarm.land()
```

## TelloException

`TelloException` is raised when a command fails.

```python
from djitellopySim import TelloException

try:
    tello.send_control_command("not_a_real_command")
except TelloException as error:
    print(error)
```

## Internal Functions

Functions that start with `_`, such as `_update_state()`, are internal helper
functions. They are part of how the simulator works inside. Students should not
call them in normal programs because they may change in future versions.
