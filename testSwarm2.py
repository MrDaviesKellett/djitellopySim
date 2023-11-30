from time import sleep
from djitellopySim import TelloSwarm

baseIP = "192.168.10." # do not modify

# MODIFY this drone list!
# ORDER MATTERS, depends how you want your drones organised...
drones = [6,4,5,7,8,20,21,11,12,13,14,15,16,17,18,19] # modify with the numbers of the drones you want to control

# do not modify
droneList = []
for drone in drones:
    droneList.append(baseIP + str(drone))

# do not modify
swarm = TelloSwarm.fromIps(droneList)

# IMAGES
UP    = "00000000000pp00000pppp000p0pp0p0000pp000000pp000000pp00000000000"
DOWN  = "00000000000pp000000pp000000pp0000p0pp0p000pppp00000pp00000000000"
RIGHT = "00000000000p000000p000000pppppp00pppppp000p00000000p000000000000"
LEFT  = "000000000000p00000000p000pppppp00pppppp000000p000000p00000000000"
FFLIP = "00ppp0000p000p000p000p000p0p0p0p0p00ppp00p000p000p00000000ppp000"
BFLIP = "000ppp0000p000p000p000p0p0p0p0p00ppp00p000p000p0000000p0000ppp00"
BLANK = "0000000000000000000000000000000000000000000000000000000000000000"
STOP  = "00000000000rr00000rrrr000rrrrrr000rrrrrr0000rrrr00000rr000000000"

# GROUPS

BACKROW   = [0, 1, 2, 3]
BACK2ROW  = [4, 5, 6, 7]
FRONT2ROW = [8, 9, 10,11]
FRONTROW  = [12,13,14,15]
LEFTROW   = [0, 4, 8, 12]
LEFT2ROW  = [1, 5, 9, 13]
RIGHT2ROW = [2, 6, 10,14]
RIGHTROW  = [3, 7, 11,15]
MIDDLE    = [5, 6, 9, 10]
OUTER     = [0,1,2,3,7,11,15,14,13,12,8,4]
ODD       = [1,3,5,7,9,11,13,15]
EVEN      = [0,2,4,6,8,10,12,14]

swarm.connect()
sleep(0.2) # wait for 0.2 of a second before sending the next command
swarm.parallel(lambda i, tello: tello.send_command_without_return("EXT mled g " + BLANK))
sleep(0.2)

# Mr Davies' Routine

def doThis(index, tello):
    # 15 is max index, max time is 8.5s
    sleep( 1 + index * 0.5)
    tello.takeoff()
    sleep(8) # plenty of time for the drone to carry out the command (as there's no return)
    tello.send_command_without_return("EXT mled g " + STOP)
    sleep( 1 + (len(drones)-index) * 0.5) # wait the remaining time

sleep(5)
swarm.parallel(lambda i, tello: doThis(i, tello))
sleep(5)

def doDifferent(index, tello):
    # PART 1: BACK to FRONT swap
    if index in BACKROW:
        tello.send_command_without_return("EXT mled g " + UP)
        sleep(1)
        tello.move_up(300)
        sleep(10) # trying to re-sync all the groups
        tello.send_command_without_return("EXT mled g " + STOP)
        sleep(1)   
        tello.move_forward(400)
    elif index in BACK2ROW:
        sleep(1) # this group goes 1 second later
        tello.send_command_without_return("EXT mled g " + UP)
        sleep(1)
        tello.move_up(200)
        sleep(10-1) # trying to re-sync all the groups
        tello.send_command_without_return("EXT mled g " + STOP)
        sleep(1) 
        tello.move_forward(130)
    elif index in FRONT2ROW: # if the drone's index is 8, 9, 10, 11
        sleep(2) # this group goes 2 second later
        tello.send_command_without_return("EXT mled g " + UP)
        sleep(1)
        tello.move_up(100)
        sleep(10-2) # trying to re-sync all the groups
        tello.send_command_without_return("EXT mled g " + STOP)
        sleep(1)
        tello.move_backward(130)
    elif index in FRONTROW:
        sleep(3) # this group goes 3 second later
        tello.send_command_without_return("EXT mled g " + UP)
        sleep(1)
        sleep(10-3) # trying to re-sync all the groups
        tello.send_command_without_return("EXT mled g " + STOP)
        sleep(1)
        tello.move_backward(400)

    sleep(8)
    tello.send_command_without_return("EXT mled g " + BLANK)

    if index in BACKROW:
        tello.move_down(300)
    elif index in BACK2ROW:
        tello.move_down(200)
    elif index in FRONT2ROW:
        tello.move_down(100)
    elif index in FRONTROW:
        pass

    # PART 2: up down odd and even
    sleep(8)
    for _ in range(4):
        if index in ODD:
            tello.send_command_without_return("EXT mled g " + UP)
            sleep(0.1)
            tello.move_up(50)
            sleep(1)
            tello.send_command_without_return("EXT mled g " + DOWN)
            sleep(0.1)
            tello.move_down(50)
        elif index in EVEN:
            tello.send_command_without_return("EXT mled g " + UP)
            sleep(0.1)
            tello.move_down(50)
            sleep(1)
            tello.send_command_without_return("EXT mled g " + DOWN)
            sleep(0.1)
            tello.move_up(50)
        sleep(1)

    # PART 3: LEFT RIGHT SWAP
    if index in LEFTROW:
        tello.send_command_without_return("EXT mled g " + UP)
        sleep(0.1)
        tello.move_up(300)
        sleep(8)
        tello.send_command_without_return("EXT mled g " + STOP)  
        sleep(0.1)
        tello.move_right(400)
    elif index in LEFT2ROW:
        tello.send_command_without_return("EXT mled g " + UP)
        sleep(0.1)
        tello.move_up(200)
        sleep(8)
        tello.send_command_without_return("EXT mled g " + STOP) 
        sleep(0.1)
        tello.move_right(130)
    elif index in RIGHT2ROW: # if the drone's index is 8, 9, 10, 11
        tello.send_command_without_return("EXT mled g " + UP)
        sleep(0.1)
        tello.move_up(100)
        sleep(8)
        tello.send_command_without_return("EXT mled g " + STOP) 
        sleep(0.1)
        tello.move_left(130)
    elif index in RIGHTROW:
        tello.send_command_without_return("EXT mled g " + UP)
        sleep(8)
        tello.send_command_without_return("EXT mled g " + STOP)
        sleep(0.1) 
        tello.move_left(400)
    
    sleep(8)
    tello.send_command_without_return("EXT mled g " + BLANK)

    if index in LEFTROW:
        tello.move_down(300)
    elif index in LEFT2ROW:
        tello.move_down(200)
    elif index in RIGHT2ROW:
        tello.move_down(100)
    elif index in RIGHTROW:
        pass

    # PART 4: PULSE
    sleep(8)
    for _ in range(4):
        if index in MIDDLE:
            tello.send_command_without_return("EXT mled g " + UP)
            sleep(0.1)
            tello.move_up(50)
            sleep(1)
            tello.send_command_without_return("EXT mled g " + DOWN)
            sleep(0.1)
            tello.move_down(50)
        elif index in OUTER:
            tello.send_command_without_return("EXT mled g " + UP)
            sleep(0.1)
            tello.move_down(50)
            sleep(1)
            tello.send_command_without_return("EXT mled g " + DOWN)
            sleep(0.1)
            tello.move_up(50)
        sleep(1)

    # PART 5: Rotate
    ''' CURRENT ARRANGEMENT:
    [[15,14,13,12]
     [11,10,9 ,8 ]
     [7 ,6 ,5 ,4 ]
     [3, 2, 1, 0]]
    '''
    if index in [15,14,13,6]:
        tello.move_right(130)
    elif index in [12,8,4,10]:
        tello.move_forward(130)
    elif index in [0,1,2,9]:
        tello.move_left(130)
    elif index in [3,7,11,5]:
        tello.move_backward(130)
    sleep(8)
    ''' CURRENT ARRANGEMENT:
    [[11,15,14,13]
     [7 ,9 ,5 ,12]
     [3 ,10,6 ,8 ]
     [2, 1, 0, 4 ]]
    '''

    if index in [11,15,14,10]:
        tello.move_right(130)
    elif index in [13,12,8,9]:
        tello.move_forward(130)
    elif index in [4,0,1,5]:
        tello.move_left(130)
    elif index in [2,3,7,6]:
        tello.move_backward(130)
    sleep(8)
    ''' CURRENT ARRANGEMENT:
    [[7 ,11,15,14]
     [3 ,5 ,6 ,13]
     [2 ,9 ,10,12]
     [1, 0, 4 ,8 ]]
    '''
    
    # all drones do this after they've finished their individual part of the routine.
    tello.flip_back()
    sleep(8) # plenty of time for the drone to carry out the command (as there's no return)
    tello.land()
    
# run this commands for all drones in this swarm
# passing the index of the drone and the drone itself as parameters
swarm.parallel(lambda i, tello: doDifferent(i, tello))
sleep(30) # sleep long enough for this command to end...

# FINSIH SWARMING

# keep the drones cool between routines!
swarm.parallel(lambda i, tello: tello.send_command_without_return("motoron"))