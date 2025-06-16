import math
import random
import asyncio
import Sensors
from collections import Counter


def calculate_distance(point_a, point_b):
    distance = math.sqrt((point_b['x'] - point_a['x']) ** 2 +
                         (point_b['y'] - point_a['y']) ** 2 +
                         (point_b['z'] - point_a['z']) ** 2)
    return distance


class DoNothing:
    """
    Does nothing
    """
    def __init__(self, a_agent):
        self.a_agent = a_agent
        self.rc_sensor = a_agent.rc_sensor
        self.i_state = a_agent.i_state

    async def run(self):
        # print("Doing nothing")
        await asyncio.sleep(1)
        return True

class ForwardDist:
    """
        Moves forward a certain distance specified in the parameter "dist".
        If "dist" is -1, selects a random distance between the initial
        parameters of the class "d_min" and "d_max"
    """
    STOPPED = 0
    MOVING = 1
    END = 2

    def __init__(self, a_agent, dist, d_min, d_max):
        self.a_agent = a_agent
        self.rc_sensor = a_agent.rc_sensor
        self.i_state = a_agent.i_state
        self.original_dist = dist
        self.target_dist = dist
        self.d_min = d_min
        self.d_max = d_max
        self.starting_pos = a_agent.i_state.position
        self.state = self.STOPPED

    async def run(self):
        try:
            previous_dist = 0.0  # Used to detect if we are stuck
            while True:
                if self.state == self.STOPPED:
                    # starting position before moving
                    self.starting_pos = self.a_agent.i_state.position
                    # Before start moving, calculate the distance we want to move
                    if self.original_dist < 0:
                        self.target_dist = random.randint(self.d_min, self.d_max)
                    else:
                        self.target_dist = self.original_dist
                    
                    # Start moving
                    await self.a_agent.send_message("action", "mf")
                    self.state = self.MOVING

                elif self.state == self.MOVING:
                    # If we are moving
                    await asyncio.sleep(0.5)  # Wait for a little movement
                    current_dist = calculate_distance(self.starting_pos, self.i_state.position)

                    if current_dist >= self.target_dist:  # Check if we already have covered the required distance
                        await self.a_agent.send_message("action", "ntm")
                        self.state = self.STOPPED
                        return True
                    
                    elif previous_dist == current_dist:  # We are not moving
                        await self.a_agent.send_message("action", "ntm")
                        self.state = self.STOPPED
                        return False
                    previous_dist = current_dist
                else:
                    print("Unknown state: " + str(self.state))
                    return False
        except asyncio.CancelledError:
            print("***** TASK Forward CANCELLED")
            await self.a_agent.send_message("action", "ntm")
            self.state = self.STOPPED

class BackwardDist:
    """
        Moves Backward a certain distance specified in the parameter "dist".
        If "dist" is -1, selects a random distance between the initial
        parameters of the class "d_min" and "d_max"
    """
    STOPPED = 0
    MOVING = 1
    END = 2

    def __init__(self, a_agent, dist, d_min, d_max):
        self.a_agent = a_agent
        self.rc_sensor = a_agent.rc_sensor
        self.i_state = a_agent.i_state
        self.original_dist = dist
        self.target_dist = dist
        self.d_min = d_min
        self.d_max = d_max
        self.starting_pos = a_agent.i_state.position
        self.state = self.STOPPED

    async def run(self):
        try:
            previous_dist = 0.0  # Used to detect if we are stuck
            while True:
                if self.state == self.STOPPED:
                    # starting position before moving
                    self.starting_pos = self.a_agent.i_state.position
                    # Before start moving, calculate the distance we want to move
                    if self.original_dist < 0:
                        self.target_dist = random.randint(self.d_min, self.d_max)
                    else:
                        self.target_dist = self.original_dist
                    
                    # Start moving
                    print(f"Starting movement to target distance: {self.target_dist}")
                    await self.a_agent.send_message("action", "mb")
                    self.state = self.MOVING

                elif self.state == self.MOVING:
                    # If we are moving
                    await asyncio.sleep(0.5)  # Wait for a little movement
                    current_dist = calculate_distance(self.starting_pos, self.i_state.position)

                    if current_dist >= self.target_dist:  # Check if we already have covered the required distance
                        await self.a_agent.send_message("action", "ntm")
                        await asyncio.sleep(0.1)
                        self.state = self.STOPPED
                        return True
                    
                    elif previous_dist == current_dist:  # We are not moving
                        await self.a_agent.send_message("action", "ntm")
                        await asyncio.sleep(0.1)
                        self.state = self.STOPPED
                        return False
                    previous_dist = current_dist
                else:
                    print("Unknown state: " + str(self.state))
                    return False
        except asyncio.CancelledError:
            print("***** TASK Forward CANCELLED")
            await self.a_agent.send_message("action", "ntm")
            self.state = self.STOPPED

class Turn:
    """
    Repeats the action of turning a random number of degrees in a random
    direction (right or left)
    """
    LEFT = -1
    RIGHT = 1

    SELECTING = 0
    TURNING = 1

    def __init__(self, a_agent):
        self.a_agent = a_agent
        self.rc_sensor = a_agent.rc_sensor
        self.i_state = a_agent.i_state

        self.current_heading = 0
        self.new_heading = 0

        self.state = self.SELECTING

    async def run(self):
        try:
            while True:
                if self.state == self.SELECTING:
                    # print("SELECTING NEW TURN")
                    rotation_direction = random.choice([-1, 1])
                    # print(f"Rotation direction: {rotation_direction}")
                    rotation_degrees = random.uniform(1, 180) * rotation_direction
                    # print("Degrees: " + str(rotation_degrees))
                    current_heading = self.i_state.rotation["y"]
                    # print(f"Current heading: {current_heading}")
                    self.new_heading = (current_heading + rotation_degrees) % 360
                    if self.new_heading == 360:
                        self.new_heading = 0.0
                    # print(f"New heading: {self.new_heading}")
                    if rotation_direction == self.RIGHT:
                        await self.a_agent.send_message("action", "tr")
                    else:
                        await self.a_agent.send_message("action", "tl")
                    self.state = self.TURNING
                elif self.state == self.TURNING:
                    # check if we have finished the rotation
                    current_heading = self.i_state.rotation["y"]
                    final_condition = abs(current_heading - self.new_heading)
                    if final_condition < 5:
                        await self.a_agent.send_message("action", "nt")
                        current_heading = self.i_state.rotation["y"]
                        # print(f"Current heading: {current_heading}")
                        # print("TURNING DONE.")
                        self.state = self.SELECTING
                        return True
                await asyncio.sleep(0)
        except asyncio.CancelledError:
            print("***** TASK Turn CANCELLED")
            await self.a_agent.send_message("action", "nt")

            
class RandomRoam:
    '''The Drone moves around following a particular direction for a certain duration, then changes
    direction, decides whether to stop, resumes movement accordingly, etc. All of this based on
    predetermined probabilities'''
    def __init__(self, a_agent):
        self.a_agent = a_agent
        self.rc_sensor = a_agent.rc_sensor
        self.i_state = a_agent.i_state

    async def run(self):
        try:
            await self.a_agent.send_message("action", "mf")
            # Initialize the probabilities for the different actions
            probabilities = {"resume": 0.5, "turn": 0.3, "stop": 0.2}
            while True:
                action = random.choices(list(probabilities.keys()), list(probabilities.values()))[0]
                if action == "turn":
                    sensor_hits = self.rc_sensor.sensor_rays[Sensors.RayCastSensor.HIT]
                    if sensor_hits[0] == 1 or sensor_hits[1] == 1:
                        await self.a_agent.send_message("action", "tr")
                        await asyncio.sleep(1)
                    elif sensor_hits[-1] == 1 or sensor_hits[-2] == 1:
                        await self.a_agent.send_message("action", "tl")
                        await asyncio.sleep(1)
                    else:
                        await self.a_agent.send_message("action", "tl")
                        await asyncio.sleep(1)
                    await self.a_agent.send_message("action", "nt")
                elif action == "stop":
                    await self.a_agent.send_message("action", "stop")
                elif action == "resume":
                    await self.a_agent.send_message("action", "mf")
                    await asyncio.sleep(3)
        except asyncio.CancelledError:
            print("***** TASK RandomRoam CANCELLED")
            await self.a_agent.send_message("action", "stop")
import random  


class Avoid:
    '''The Drone advances while avoiding obstacles, ensuring it does not collide with objects,
    including exterior walls.'''
    
    def __init__(self, a_agent):
        self.a_agent = a_agent
        self.rc_sensor = a_agent.rc_sensor
        self.i_state = a_agent.i_state
    
    async def run(self):
        try:
            print("AVOID (from goals)")
            await self.a_agent.send_message("action", "mf")
            while True:
                sensor_hits = self.rc_sensor.sensor_rays[Sensors.RayCastSensor.HIT]
                
                if any(ray_hit == 1 for ray_hit in sensor_hits):             
                    await self.a_agent.send_message("action", "stop")
                    if sensor_hits[0] == 1 and sensor_hits[1] == 1 and sensor_hits[2] == 1 and sensor_hits[3] == 1 and sensor_hits[4] == 1:
                        await self.a_agent.send_message("action", "tr") #all sensors hit. move right (could move left too)
                        await asyncio.sleep(1)
                    elif sensor_hits[0] == 1 and sensor_hits[4] == 1 and sensor_hits[2] == 0:  #obstacles in left and right. center is free
                        await self.a_agent.send_message("action", "mf")
                        await asyncio.sleep(1)
                    elif sensor_hits[0] == 1 or sensor_hits[1] == 1: #obstacles in left. move right
                        await self.a_agent.send_message("action", "tr")
                        await asyncio.sleep(0.1)
                    elif sensor_hits[-1] == 1 or sensor_hits[-2] == 1: #obstacles in right. move left
                        await self.a_agent.send_message("action", "tl")
                        await asyncio.sleep(0.1)
                    else:
                        await self.a_agent.send_message("action", "tl") #if none of the above, move left
                        await asyncio.sleep(0.1)
                    await self.a_agent.send_message("action", "nt") #stop the turn
                    await self.a_agent.send_message("action", "mf") #MOVE FORWARD
                    await asyncio.sleep(0.2)
                else: #if no obstacles detected
                    await asyncio.sleep(0.2) 
                    random_turn = random.choice(["tr", "tl"])       
                    await self.a_agent.send_message("action", random_turn)  #random turn (left or right) for a short period of time
                    await asyncio.sleep(0.1)
                    await self.a_agent.send_message("action", "nt")
                
        except asyncio.CancelledError:
            print("***** TASK Avoid CANCELLED")
            await self.a_agent.send_message("action", "stop")
            
class AvoidForCritters:
    '''The Critter advances while avoiding obstacles, ensuring it does not collide with objects,
    including exterior walls. Considers the presence of other critters in the environment.'''
    
    def __init__(self, a_agent):
        self.a_agent = a_agent
        self.rc_sensor = a_agent.rc_sensor
        self.i_state = a_agent.i_state
    
    async def run(self):
        try:
            print("AvoidForCritters (from goals)")
            await self.a_agent.send_message("action", "mf")
            while True:
                sensor_hits = self.rc_sensor.sensor_rays[Sensors.RayCastSensor.HIT]
                sensor_info = self.rc_sensor.sensor_rays[Sensors.RayCastSensor.OBJECT_INFO]

                critter_nearby = any(info and info.get("tag") == "CritterMantaRay" for info in sensor_info)
                if critter_nearby: ## Check if any of the sensors detected a critter
                    print("      From Avoid: Another critter detected! Swerving...")
                    await self.a_agent.send_message("action", "stop")
                    await self.a_agent.send_message("action", "tr") # Move right
                    await asyncio.sleep(0.5)
                    await self.a_agent.send_message("action", "mf") # Move forward
                    await asyncio.sleep(0.5)

                elif any(ray_hit == 1 for ray_hit in sensor_hits):             
                    await self.a_agent.send_message("action", "stop")
                    if sensor_hits[0] == 1 and sensor_hits[1] == 1 and sensor_hits[2] == 1 and sensor_hits[3] == 1 and sensor_hits[4] == 1:
                        await self.a_agent.send_message("action", "tr") #all sensors hit. move right (could move left too)
                        await asyncio.sleep(1)
                    elif sensor_hits[0] == 1 and sensor_hits[4] == 1 and sensor_hits[2] == 0:  #obstacles in left and right. center is free
                        await self.a_agent.send_message("action", "mf")
                        await asyncio.sleep(1)
                    elif sensor_hits[0] == 1 or sensor_hits[1] == 1: #obstacles in left. move right
                        await self.a_agent.send_message("action", "tr")
                        await asyncio.sleep(0.1)
                    elif sensor_hits[-1] == 1 or sensor_hits[-2] == 1: #obstacles in right. move left
                        await self.a_agent.send_message("action", "tl")
                        await asyncio.sleep(0.1)
                    else:                     #if none of the above, move backwards and turn a bit to the left
                        await self.a_agent.send_message("action", "mb")
                        await asyncio.sleep(0.2)
                        await self.a_agent.send_message("action", "tl")
                        await asyncio.sleep(0.1)
                    await self.a_agent.send_message("action", "nt")
                    await self.a_agent.send_message("action", "mf") #MOVE FORWARD
                    await asyncio.sleep(0.2)
                else: #if no obstacles detected
                    await asyncio.sleep(0.2) 
                    random_turn = random.choice(["tr", "tl"])       
                    await self.a_agent.send_message("action", random_turn)  
                    await asyncio.sleep(0.1)
                    await self.a_agent.send_message("action", "nt")

        except asyncio.CancelledError:
            print("***** TASK AvoidForCritters CANCELLED")
            await self.a_agent.send_message("action", "stop")

