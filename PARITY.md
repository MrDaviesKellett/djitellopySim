# DJITelloPy 2.5.0 Parity

This simulator targets the public `djitellopy` 2.5.0 API published on PyPI on
2023-06-09. It implements local, deterministic behavior where a real drone would
normally communicate over UDP.

## Implemented Public Surface

- Construction and lifecycle: `Tello`, `TelloException`, `TelloSwarm`,
  `BackgroundFrameRead`, `connect`, `end`, `reboot`, `emergency`
- Core movement: `takeoff`, `land`, `move`, `move_up`, `move_down`,
  `move_left`, `move_right`, `move_forward`, `move_back`, `move_backward`,
  `rotate_clockwise`, `rotate_counter_clockwise`, `flip`, `flip_left`,
  `flip_right`, `flip_forward`, `flip_back`
- Advanced motion shims: `go_xyz_speed`, `curve_xyz_speed`,
  `go_xyz_speed_mid`, `curve_xyz_speed_mid`, `go_xyz_speed_yaw_mid`
- Command helpers: `send_command_with_return`, `send_command_without_return`,
  `send_control_command`, `send_read_command`, `send_read_command_int`,
  `send_read_command_float`, `raise_result_error`, `parse_state`
- State accessors: `get_current_state`, `get_state_field`,
  `get_mission_pad_id`, `get_mission_pad_distance_x`,
  `get_mission_pad_distance_y`, `get_mission_pad_distance_z`, `get_pitch`,
  `get_roll`, `get_yaw`, `get_speed_x`, `get_speed_y`, `get_speed_z`,
  `get_acceleration_x`, `get_acceleration_y`, `get_acceleration_z`,
  `get_lowest_temperature`, `get_highest_temperature`, `get_temperature`,
  `get_height`, `get_distance_tof`, `get_barometer`, `get_flight_time`,
  `get_battery`
- Query methods: `query_speed`, `query_battery`, `query_flight_time`,
  `query_height`, `query_temperature`, `query_attitude`, `query_barometer`,
  `query_distance_tof`, `query_wifi_signal_noise_ratio`, `query_sdk_version`,
  `query_serial_number`, `query_active`
- SDK configuration: `send_keepalive`, `turn_motor_on`, `turn_motor_off`,
  `initiate_throw_takeoff`, `enable_mission_pads`, `disable_mission_pads`,
  `set_mission_pad_detection_direction`, `set_speed`, `send_rc_control`,
  `set_wifi_credentials`, `connect_to_wifi`, `set_network_ports`,
  `change_vs_udp`, `set_video_bitrate`, `set_video_resolution`,
  `set_video_fps`, `set_video_direction`, `send_expansion_command`
- Video API shape: `streamon`, `streamoff`, `get_udp_video_address`,
  `get_frame_read`
- Swarm operations: `fromFile`, `fromIps`, `parallel`, `sequential`, `sync`,
  `land`, `end`, `__iter__`, `__len__`, dynamic parallel method dispatch

## Intentional Simulator Differences

- Network sockets are not opened. Commands are interpreted locally and return
  simulated `ok`, query, or error responses.
- Video frames are generated placeholder NumPy arrays, not decoded drone H.264
  frames.
- Mission pad movement is treated as regular relative movement. Pad detection
  values are synthetic.
- Curve movement is approximated as two linear segments. It does not validate
  arc radius constraints.
- Wi-Fi, port, reboot, SDK, serial number, and active status commands are
  simulated metadata only.
- The extension board LED command changes the rendered top LED. Matrix LED
  commands are stored on the drone state but are not rendered yet.

## Remaining Gaps For 1:1 Behavioral Parity

- Exact UDP timing, retry failure modes, and socket response queue behavior.
- Real video streaming via PyAV and queue semantics under packet loss.
- Full Tello SDK range validation and real error strings for every invalid
  command argument.
- Accurate mission pad coordinate transforms and dual-pad `jump` behavior.
- Physics-grade curve paths, acceleration, yaw/pitch/roll, and wind modeling.
- Rendering of Tello Talent matrix LED patterns.
