from djitellopySim import TelloSwarm

swarm = TelloSwarm.fromFile('ip.txt')

swarm.connect()
swarm.takeoff()
swarm.move_forward(100)
swarm.rotate_clockwise(90)
swarm.move_backward(100)
swarm.rotate_counter_clockwise(90)
swarm.sequential(lambda i, tello: tello.move_left(i * 30 + 30))
swarm.move_right(100)
swarm.move_up(100)
swarm.move_down(100)
swarm.land()
