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



