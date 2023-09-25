from djitellopySim import Tello
from time import sleep

myTello = Tello()
myTello.takeoff()
myTello.move_forward(100)
myTello.rotate_clockwise(90)
myTello.move_backward(100)
myTello.rotate_counter_clockwise(90)
myTello.move_left(100)
myTello.move_right(100)
myTello.move_up(100)
myTello.move_down(100)
myTello.land()
