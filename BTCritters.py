#################################################
# 2nd scenario: Scenario Critters
#################################################


import asyncio
import py_trees as pt
from py_trees import common
import math
import random
import Sensors
import Goals_BT
import time


'''
Behavior:
● Default State (Roaming):
    ○ The critter roams aimlessly, avoiding obstacles.
● Astronaut Detection:
    ○ If the critter detects the astronaut, it starts following her and attempts
    to bite (touch the astronaut).
    ○ Biting the astronaut implies the astronaut is stunned for 5 seconds,
    and if she had flowers in her inventory, she will lose one (this behavior
    is automatic and managed by AAPE, you don’t have to program it in
    Python)
    ○ After biting the astronaut, the critter has to move away and allow the
    astronaut to recover.
    ○ If it loses contact, it resumes roaming.

TIPS:
● If you want to try with multiple critters, use the Spawner.py tool and the two Spawn Areas (“HarvestZone” or “SmallHarvestZone”).
● Use a manually controlled Astronaut to test your Critters.
'''
# Behavior Tree Critter
class BTRoamOrChase:
    def __init__(self, aagent):
        self.aagent = aagent # refference to agent
        self.create_behavior_tree() # initialize the bt

    def create_behavior_tree(self):
        # Sequence: detect and move to astronaut
        chase_astronaut = pt.composites.Sequence("ChaseAstronaut", memory=True)
        chase_astronaut.add_children([
            BN_DetectAstronaut(self.aagent),
            BN_TurnToAstronaut(self.aagent),
            BN_MoveToAstronaut(self.aagent),
            BN_MoveAwayFromAstronaut(self.aagent)
        ])

        wander = pt.composites.Sequence("Wander", memory=True)
        wander.add_children([BN_Wander(self.aagent)])

        # Root: Selector, tries chasing first, otherwise roams
        self.root = pt.composites.Selector("RoamOrChase", memory=False)  
        self.root.add_children([
            chase_astronaut,
            wander
        ])

        self.behaviour_tree = pt.trees.BehaviourTree(self.root)

    async def tick(self):
        try:
            self.behaviour_tree.tick()
            await asyncio.sleep(0.1)
        except Exception as e:
            print(f"[BTRoamOrChase] Tick error: {e}")
            raise

    def stop_behaviour_tree(self):
        def set_invalid(node):
            node.status = pt.common.Status.INVALID
            for child in getattr(node, "children", []):
                set_invalid(child)
        set_invalid(self.root)

############################################################################# NODES #############################################################################
class BN_Wander(pt.behaviour.Behaviour):
    def __init__(self, aagent):
        super().__init__("Wander")
        self.my_agent = aagent
        self.wander_task = None
        self.is_wandering = False

    def initialise(self):
        if not self.is_wandering:
            self.wander_task = asyncio.create_task(Goals_BT.AvoidForCritters(self.my_agent).run()) #avoid goal for critters (includes critter avoidance)
            self.is_wandering = True
            # print("Started wandering")

    def update(self):
        sensor_info = self.my_agent.rc_sensor.sensor_rays[Sensors.RayCastSensor.OBJECT_INFO]
        for i in range(len(sensor_info)):
            if sensor_info[i] and sensor_info[i]["tag"] == "Astronaut":
                print("      From critter: Astronaut detected during wandering! BN_Wander SUCCESS.")
                return pt.common.Status.SUCCESS  # Exit wander and move to detect astronaut
        if not self.is_wandering:
            self.initialise()
        return pt.common.Status.RUNNING  # Keep wandering

    def terminate(self, new_status: common.Status):
        if self.wander_task and not self.wander_task.done():
            self.wander_task.cancel()
            print("      From critter: Stopped wandering")
        self.is_wandering = False


class BN_DetectAstronaut(pt.behaviour.Behaviour):
    print("      From critter: BNdetectAstronaut")
    def __init__(self, aagent):
        super().__init__("BN_DetectAstronaut")
        self.aagent = aagent

    def update(self):   
        sensor_info = self.aagent.rc_sensor.sensor_rays[Sensors.RayCastSensor.OBJECT_INFO]
        for i in range(len(sensor_info)):
            if sensor_info[i] and sensor_info[i]["tag"] == "Astronaut": #look for astronaut in the sensor info
                print("      From critter: Detected astronaut")
                return pt.common.Status.SUCCESS
        return pt.common.Status.FAILURE # no astronaut detected
    

sensor_degree = {0:-45, 1:-22.5, 2:0, 3:22.5, 4:45}
# node: turn to astronaut
class BN_TurnToAstronaut(pt.behaviour.Behaviour):
    def __init__(self, aagent):
        super().__init__("TurnToFlower")
        self.my_agent = aagent
        self.task = None
        self.turn_angle = None
        self.new_heading = None

    def initialise(self):
        print('      From critter: Turning to astronaut ...')
        sensor_info = self.my_agent.rc_sensor.sensor_rays[Sensors.RayCastSensor.OBJECT_INFO]
        min_distance = 10000
        turn_angle = None

        for i in range(len(sensor_info)):
            if sensor_info[i] and sensor_info[i]["tag"] == "Astronaut":
                if i == 2: ## Front ray
                    print("      From critter: astronaut detected from the front ray SUCCESS")
                    self.new_heading = self.my_agent.i_state.rotation["y"]
                    return pt.common.Status.SUCCESS
                if sensor_info[i]["distance"] < min_distance:
                    min_distance = sensor_info[i]["distance"]
                    turn_angle = sensor_degree[i]

        if turn_angle is not None:
            current_heading = self.my_agent.i_state.rotation["y"]
            self.new_heading = (current_heading + turn_angle) % 360
            if turn_angle > 0:
                print(f"      From critter: TR__Turning to flower at angle {turn_angle}")
                self.task = asyncio.create_task(self.my_agent.send_message("action", "tr"))
            else:
                print(f"      From critter: TL__Turning to flower at angle {turn_angle}")
                self.task = asyncio.create_task(self.my_agent.send_message("action", "tl"))
        else:
            print("      From critter: No astronaut found to turn to.")
            self.task = None
            self.new_heading = None  

    def update(self):
        def angle_difference(a, b):
            diff = (a - b + 180) % 360 - 180
            return diff

        if self.new_heading is None:
            return pt.common.Status.FAILURE  # No target

        current_heading = self.my_agent.i_state.rotation["y"]
        if abs(angle_difference(current_heading, self.new_heading)) < 5:
            print('      From critter: Turned to astronaut. SUCCESS')
            self.task = asyncio.create_task(self.my_agent.send_message("action", "nt"))
            return pt.common.Status.SUCCESS
            
        turn_speed = "tl" if angle_difference(current_heading, self.new_heading) > 0 else "tr"
        # Only send new command if not already turning
        if not self.task or self.task.done():
            self.task = asyncio.create_task(self.my_agent.send_message("action", turn_speed))
        return pt.common.Status.RUNNING
    
    def terminate(self, new_status: common.Status):
        if self.task and not self.task.done():
            self.task.cancel()
        self.task = None

#node: move to astronaut
class BN_MoveToAstronaut(pt.behaviour.Behaviour):
    print("      From critter: BNMoveToAstronaut")
    def __init__(self, aagent):
        super().__init__("BN_MoveToAstronaut")
        self.my_agent = aagent
        self.task = None  

    def initialise(self):
        sensor_info = self.my_agent.rc_sensor.sensor_rays[Sensors.RayCastSensor.OBJECT_INFO]
        closest_astronaut = None
        min_distance = float('inf')
        
        self.task = asyncio.create_task(self.my_agent.send_message("action", "nt"))
        for i in range(len(sensor_info)):
            if sensor_info[i] and sensor_info[i]["tag"] == "Astronaut":
                if sensor_info[i]["distance"] < min_distance: #look for the closest astronaut
                    min_distance = sensor_info[i]["distance"]
                    closest_astronaut = sensor_info[i]

        if closest_astronaut:
            self.task = asyncio.create_task(Goals_BT.ForwardDist(self.my_agent, min_distance-1.4, 1, 100).run()) #move forward to the astronaut with a margin to avoid collision
            print(f"      From critter: Moving to astronaut at distance {min_distance}")
        else:
            print("      From critter: No astronaut found to move to.")
            return pt.common.Status.FAILURE  # No target

    def update(self):
        if not self.task:
            return pt.common.Status.FAILURE
        if not self.task.done():
            return pt.common.Status.RUNNING
        if self.task.exception():
            print(f"Exception while moving to astronaut: {self.task.exception()}")
            return pt.common.Status.FAILURE
        
        sensor_info = self.my_agent.rc_sensor.sensor_rays[Sensors.RayCastSensor.OBJECT_INFO]
        for i in range(len(sensor_info)):
            if sensor_info[i] and sensor_info[i]["tag"] == "Astronaut":
                if sensor_info[i]["distance"] < 0.9:
                    print(f"      From critter: Arrived at astronaut. SUCCESS")
                    return pt.common.Status.SUCCESS
        print("      From critter: No astronaut detected after moving. FAILURE")
        # print(sensor_info)
        return pt.common.Status.FAILURE 

    def terminate(self, new_status: common.Status):
        if self.task and not self.task.done():
            self.task.cancel()
        self.task = None
        
# node: move away from astronaut if bitten       
class BN_MoveAwayFromAstronaut(pt.behaviour.Behaviour):   
    def __init__(self, aagent):
        super().__init__("BN_MoveAwayFromAstronaut")
        self.my_agent = aagent
        self.task = None  

    def initialise(self):
        distance = 10
        self.task = asyncio.create_task(self.my_agent.send_message("action", "nt"))
        self.task = asyncio.create_task(Goals_BT.BackwardDist(self.my_agent, distance, 1, 100).run())
        
        # turn to avoid critter from continuously attacking astronaut
        current_heading = int(self.my_agent.i_state.rotation["y"])
        self.new_heading = (current_heading + 60) % 360
        self.task = asyncio.create_task(self.my_agent.send_message("action", "tr"))
        print(f"      From critter: Moving AWAY")

    def update(self):
        def angle_difference(a, b):
            diff = (a - b + 180) % 360 - 180
            return abs(diff)

        current_heading = self.my_agent.i_state.rotation["y"]
        if angle_difference(current_heading, self.new_heading) < 5:
            print('Turned away from critter. SUCCESS')
            self.task = asyncio.create_task(self.my_agent.send_message("action", "nt"))
            return pt.common.Status.SUCCESS
        if not self.task:
            return pt.common.Status.FAILURE
        if not self.task.done():
            return pt.common.Status.RUNNING
        if self.task.exception():
            print(f"Exception while moving to astronaut: {self.task.exception()}")
            return pt.common.Status.FAILURE
        else:
            return pt.common.Status.FAILURE
            
    def terminate(self, new_status: common.Status):
        if self.task and not self.task.done():
            self.task.cancel()
        self.task = None    