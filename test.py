from djitellopySim import Tello
from time import sleep

myTello = Tello()
myTello.takeoff()

# what would this do? draw the drone's flight path
from random import randint

# fly in a square

for i in range(4): # LOOP
    myTello.move_forward(100)
    myTello.rotate_clockwise(90)

myTello.send_command_without_return("EXT led 0 255 255")
myTello.flip_back()
sleep(2)
myTello.send_command_without_return("EXT led 255 0 255")
myTello.flip_back()
sleep(2)
myTello.land()



