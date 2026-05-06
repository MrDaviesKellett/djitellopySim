from time import sleep

from djitellopySim import Tello


tello = Tello()
tello.connect()
tello.send_control_command("racegates 5 slalom")
tello.send_control_command("camerafollow on")
tello.send_control_command("racehints distance on")
tello.send_control_command("racehints height on")
tello.takeoff()

for _ in range(8):
    print(tello.get_race_gate_measurements())
    sleep(1)

tello.send_control_command("cameraoverview")
sleep(2)
tello.land()
