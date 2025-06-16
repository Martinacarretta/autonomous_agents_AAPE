
#################################################
# 3rd scenario: Collect & Run
#################################################
import asyncio
import py_trees as pt
from py_trees import common
import Goals_BT
import Sensors

'''
Behavior:
● Wandering & Detection:
    ○ The astronaut wanders the outpost searching for alien flowers (tag: AlienFlower).
    ○ When a flower is detected, she moves toward it and automatically collects it (added to her inventory).
● Inventory Limit:
    ○ She can carry only two flowers at a time.
    ○ When her inventory is full, she must return to the Base Outpost to unload (action:leave,AlienFlower,2).
● Returning to Base:
    ○ To return, she uses the NavMesh system (action:walk_to,Base).
    ○ For testing purposes only, she may also use instant teleportation (action:teleport_to,Base) 
    to speed up the process (since the return trip in this scenario is always safe).

!! We want the Astronaut to replicate the same behavior demonstrated in the "Alone" scenario, 
but now with an added requirement: active avoidance of the Critters.
'''

# Node: Detect frozen state
class BN_DetectFrozen(pt.behaviour.Behaviour):
    def __init__(self, aagent):
        self.my_goal = None
        super(BN_DetectFrozen, self).__init__("BN_DetectFrozen")
        self.my_agent = aagent
        self.i_state = aagent.i_state
    def initialise(self):
        pass
    def update(self):
        if self.my_agent.i_state.isFrozen == True:
            print('Frozen branch. astronaut is frozen!!!')
            return pt.common.Status.SUCCESS
        return pt.common.Status.FAILURE
    def terminate(self, new_status: common.Status):
        pass

# Node: Do Nothing
class BN_DoNothing(pt.behaviour.Behaviour):
    def __init__(self, aagent):
        super().__init__("DoNothing")
        self.my_agent = aagent
        self.task = None  

    def initialise(self):
        self.task = asyncio.create_task(Goals_BT.DoNothing(self.my_agent).run())

    def update(self):
        if self.task.done():
            print("DoNothing task completed.")
            return pt.common.Status.SUCCESS
        # print("Doint nothing... RUNNING")
        return pt.common.Status.RUNNING  

# Node: Detect Critter nearby
class BN_DetectCritter(pt.behaviour.Behaviour):
    def __init__(self, aagent):
        super().__init__("DetectCritter")
        self.my_agent = aagent

    def update(self):
        sensor_info = self.my_agent.rc_sensor.sensor_rays[Sensors.RayCastSensor.OBJECT_INFO]
        for i in range(len(sensor_info)):
            if sensor_info[i] and sensor_info[i]["tag"] == "CritterMantaRay":
                print("BN_DetectCritter SUCCESS")
                return pt.common.Status.SUCCESS
        print("BN_DetectCritter FAILURE")
        return pt.common.Status.FAILURE

# Node: Move away from Critter (move backward)
class BN_MoveAwayFromCritter(pt.behaviour.Behaviour):   
    def __init__(self, aagent):
        super().__init__("BN_MoveAwayFromCritter")
        self.my_agent = aagent
        self.task = None  

    def initialise(self):
        distance = 6
        self.task = asyncio.create_task(self.my_agent.send_message("action", "nt"))
        self.task = asyncio.create_task(Goals_BT.BackwardDist(self.my_agent, distance, 1, 100).run())

    def update(self):
        if self.my_agent.i_state.isFrozen:
            print('Frozen...')
            return pt.common.Status.FAILURE
        if not self.task:
            return pt.common.Status.FAILURE
        if not self.task.done():
            return pt.common.Status.RUNNING
        if self.task.exception():
            print(f"Exception while moving away from critter: {self.task.exception()}")
            return pt.common.Status.FAILURE
        print("Astronaut moved away from critter. SUCCESS")
        self.task = asyncio.create_task(self.my_agent.send_message("action", "stop"))
        return pt.common.Status.SUCCESS

    def terminate(self, new_status: common.Status):
        if self.task and not self.task.done():
            self.task.cancel()
        self.task = None    
    
# Node: Turn away from Critter (turn left or right)
class BN_TurnAwayFromCritter(pt.behaviour.Behaviour):
    def __init__(self, aagent):
        super().__init__("TurnAwayCritter")
        self.my_agent = aagent
        self.task = None
        self.turn_angle = None
        self.new_heading = None

    def initialise(self):
        current_heading = int(self.my_agent.i_state.rotation["y"])
        self.task = asyncio.create_task(self.my_agent.send_message("action", "nt"))

        self.turn_angle = 60 
        sensor_hits = self.my_agent.rc_sensor.sensor_rays[Sensors.RayCastSensor.HIT]
        # check sensor hits for a better performance
        if sensor_hits[0] == 1 or  sensor_hits[1] == 1 or sensor_hits[2] == 1: # left side blocked
            self.new_heading = (current_heading + self.turn_angle) % 360
            self.task = asyncio.create_task(self.my_agent.send_message("action", "tr"))
        elif sensor_hits[3] == 1 or sensor_hits[4] == 1: #right side blocked
            self.new_heading = (current_heading - self.turn_angle) % 360
            self.task = asyncio.create_task(self.my_agent.send_message("action", "tl"))
        else: # no side blocked. turn left
            self.new_heading = (current_heading - self.turn_angle) % 360
            self.task = asyncio.create_task(self.my_agent.send_message("action", "tl"))

    def update(self):
        def angle_difference(a, b):
            diff = (a - b + 180) % 360 - 180
            return abs(diff)
        current_heading = self.my_agent.i_state.rotation["y"]
        if angle_difference(current_heading, self.new_heading) < 5:
            print('Turned away from critter. SUCCESS')
            self.task = asyncio.create_task(self.my_agent.send_message("action", "nt"))
            return pt.common.Status.SUCCESS
        if self.my_agent.i_state.isFrozen:
            print('Agent frozen during turn away from critter... FAILURE')
            return pt.common.Status.FAILURE
        # print('Turning away from critter... RUNNING')
        return pt.common.Status.RUNNING

    def terminate(self, new_status: common.Status):
        if self.task and not self.task.done():
            self.task.cancel()
        self.task = None

# Node: Leave Critter (move away from critter by moving forward)
class BN_LeaveCritter(pt.behaviour.Behaviour):
    def __init__(self, aagent):
        super().__init__("MoveAwayCritter")
        self.my_agent = aagent
        self.task = None  

    def initialise(self): 
        self.task = asyncio.create_task(self.my_agent.send_message("action", "nt"))
        sensor_hits = self.my_agent.rc_sensor.sensor_rays[Sensors.RayCastSensor.HIT]
        if sensor_hits[2] == 1: #check if the front is blocked to avoid getting stuck
            print('something on front. failure moving away from critter')
            return pt.common.Status.FAILURE  
        self.task = asyncio.create_task(Goals_BT.ForwardDist(self.my_agent, 4, 1, 100).run())
       
    def update(self):
        #check if the agent is frozen
        if self.my_agent.i_state.isFrozen: 
            print('Frozen...')
            return pt.common.Status.FAILURE
        
        if not self.task:
            return pt.common.Status.FAILURE
        if not self.task.done():
            return pt.common.Status.RUNNING
        if self.task.exception():
            print(f"Exception while moving away from critter: {self.task.exception()}")
            return pt.common.Status.FAILURE
        print(f"BN_LeaveCritter SUCCESS")
        return pt.common.Status.SUCCESS

    def terminate(self, new_status: common.Status):
        if self.task and not self.task.done():
            self.task.cancel()
        self.task = None

# Node: Check if inventory is full
class BN_CheckInventoryFull(pt.behaviour.Behaviour):
    def __init__(self, aagent):
        super().__init__("CheckInventoryFull")
        self.my_agent = aagent

    def update(self):
        # Check if the inventory is full (amount >= 2
        for item in self.my_agent.i_state.myInventoryList:
            print(item["name"], item["amount"])
            if item["name"] == "AlienFlower" and item["amount"] >= 2:
                print("Inventory full")
                return pt.common.Status.SUCCESS
        return pt.common.Status.FAILURE

class BN_GoToBase(pt.behaviour.Behaviour):
    def __init__(self, aagent):
        super().__init__("GoToBase")
        self.my_agent = aagent
        self.task = None

    def initialise(self):
        print('Going to base')
        # Start the task to walk to the base
        self.task = asyncio.create_task(self.my_agent.send_message("action", "walk_to,Base"))

    def update(self):
        if self.my_agent.i_state.isFrozen == True:
            print('Frozen while going to base...') #astronaut loses one flower when frozen. 
            return pt.common.Status.FAILURE
        if self.my_agent.i_state.currentNamedLoc == "Base" and self.my_agent.i_state.onRoute == False: #astronaut in base and not going to target location
            print('Reached base. SUCCESS')
            return pt.common.Status.SUCCESS
        else:
            return pt.common.Status.RUNNING

    def terminate(self, new_status: common.Status):
        if self.task and not self.task.done():
            self.task.cancel()

# Node: Unload flowers
class BN_UnloadFlowers(pt.behaviour.Behaviour):
    def __init__(self, aagent):
        super().__init__("UnloadFlowers")
        self.my_agent = aagent
        self.unload_task = None

    def initialise(self):
        # print('Unloading flowers...')
        self.unload_task = asyncio.create_task(self.my_agent.send_message("action", "leave,AlienFlower,2"))

    def update(self):
        if not self.unload_task.done():
            print('Unloading flowers... RUNNING')
            return pt.common.Status.RUNNING  
        else:
            for item in self.my_agent.i_state.myInventoryList:
                if item["name"] == "AlienFlower":  # in case there are still flowers in the inventory return failure
                    print('failure unloading flowers...')
                    return pt.common.Status.FAILURE
            print('Unloaded flowers. SUCCESS')
            return pt.common.Status.SUCCESS

    def terminate(self, new_status: common.Status):
        if self.unload_task and not self.unload_task.done():
            self.unload_task.cancel()

# Node: Detect flower nearby
class BN_DetectFlower(pt.behaviour.Behaviour):
    def __init__(self, aagent):
        super().__init__("DetectFlower")
        self.my_agent = aagent

    def update(self):
        sensor_info = self.my_agent.rc_sensor.sensor_rays[Sensors.RayCastSensor.OBJECT_INFO]
        for i in range(len(sensor_info)):
            if sensor_info[i] and sensor_info[i]["tag"] == "AlienFlower":
                print("BN_DetectFlower SUCCESS")
                return pt.common.Status.SUCCESS
        print("BN_DetectFlower FAILURE")
        return pt.common.Status.FAILURE
    
sensor_degree = {0:-45, 1:-22.5, 2:0, 3:22.5, 4:45}
# Node: Turn to flower 
class BN_TurnToFlower(pt.behaviour.Behaviour):
    def __init__(self, aagent):
        super().__init__("TurnToFlower")
        self.my_agent = aagent
        self.task = None
        self.turn_angle = None
        self.new_heading = None

    def initialise(self):
        sensor_info = self.my_agent.rc_sensor.sensor_rays[Sensors.RayCastSensor.OBJECT_INFO]
        min_distance = 10000
        turn_angle = None

        for i in range(len(sensor_info)):
            if sensor_info[i] and sensor_info[i]["tag"] == "AlienFlower":
                if i == 2: # no turn needed. flower is in front of the astronaut
                    print("BN_TurnToFlower: flower detected in front SUCCESS")
                    self.new_heading = self.my_agent.i_state.rotation["y"]
                    return pt.common.Status.SUCCESS
                if sensor_info[i]["distance"] < min_distance: # look for the closest flower
                    min_distance = sensor_info[i]["distance"]
                    turn_angle = sensor_degree[i] # get the angle to turn to flower based on the sensor index

        if turn_angle is not None:
            current_heading = self.my_agent.i_state.rotation["y"]
            self.new_heading = (current_heading + turn_angle) % 360
            if turn_angle > 0:
                print(f"TR_Turning to flower at angle {turn_angle}")
                self.task = asyncio.create_task(self.my_agent.send_message("action", "tr"))
            else:
                print(f"TL_Turning to flower at angle {turn_angle}")
                self.task = asyncio.create_task(self.my_agent.send_message("action", "tl"))
        else:
            print("No flower found to turn to.")
            self.task = None
            self.new_heading = None  

    def update(self):
        def angle_difference(a, b):
            diff = (a - b + 180) % 360 - 180
            return abs(diff)

        if self.new_heading is None:
            return pt.common.Status.FAILURE  # No target

        current_heading = self.my_agent.i_state.rotation["y"]
        if angle_difference(current_heading, self.new_heading) < 5:
            print('Turned to flower. SUCCESS')
            self.task = asyncio.create_task(self.my_agent.send_message("action", "nt"))
            return pt.common.Status.SUCCESS

        # print('Turning to flower... RUNNING')
        return pt.common.Status.RUNNING

    def terminate(self, new_status: common.Status):
        if self.task and not self.task.done():
            self.task.cancel()
        self.task = None

# Node: Move to flower (move forward)
class BN_MoveToFlower(pt.behaviour.Behaviour):
    def __init__(self, aagent):
        super().__init__("MoveToFlower")
        self.my_agent = aagent
        self.task = None  

    def initialise(self):
        sensor_info = self.my_agent.rc_sensor.sensor_rays[Sensors.RayCastSensor.OBJECT_INFO]
        closest_flower = None
        min_distance = float('inf')
        
        self.task = asyncio.create_task(self.my_agent.send_message("action", "nt"))
        for i in range(len(sensor_info)):
            if sensor_info[i] and sensor_info[i]["tag"] == "AlienFlower":
                if sensor_info[i]["distance"] < min_distance: #choose the closest flower
                    min_distance = sensor_info[i]["distance"]
                    closest_flower = sensor_info[i]

        if closest_flower:
            self.task = asyncio.create_task(Goals_BT.ForwardDist(self.my_agent, min_distance, 1, 100).run()) #move forward to the flower
            # print(f"Moving to flower at distance {min_distance}")
        else:
            print("No flower found to move to.")

    def update(self):
        if not self.task:
            return pt.common.Status.FAILURE
        if not self.task.done():
            return pt.common.Status.RUNNING
        if self.task.exception():
            print(f"Exception while moving to flower: {self.task.exception()}")
            return pt.common.Status.FAILURE
        print(f"BN_MoveToFlower SUCCESS")
        return pt.common.Status.SUCCESS

    def terminate(self, new_status: common.Status):
        if self.task and not self.task.done():
            self.task.cancel()
        self.task = None

# Node: Collect flower (action: collect)            
class BN_CollectFlower(pt.behaviour.Behaviour):
    def __init__(self, aagent):
        super().__init__("CollectFlower")
        self.my_agent = aagent
        self.collect_task = None

    def initialise(self):
        self.collect_task = asyncio.create_task(self.my_agent.send_message("action", "collect"))

    def update(self):
        if not self.collect_task:
            return pt.common.Status.FAILURE
        if not self.collect_task.done():
            return pt.common.Status.RUNNING
        print(f"BN_CollectFlower SUCCESS")
        return pt.common.Status.SUCCESS

    def terminate(self, new_status: common.Status):
        if self.collect_task and not self.collect_task.done():
            self.collect_task.cancel()

# Node: wander        
class BN_Wander(pt.behaviour.Behaviour):
    def __init__(self, aagent):
        super().__init__("Wander")
        self.my_agent = aagent
        self.wander_task = None
        self.is_wandering = False

    def initialise(self):
        if not self.is_wandering:
            self.wander_task = asyncio.create_task(Goals_BT.Avoid(self.my_agent).run()) #execute avoid goal for better environment exploration
            self.is_wandering = True
            # print("Started wandering")

    def update(self):
        sensor_info = self.my_agent.rc_sensor.sensor_rays[Sensors.RayCastSensor.OBJECT_INFO]
        for i in range(len(sensor_info)):
            if sensor_info[i] and sensor_info[i]["tag"] == "AlienFlower":
                print("Flower detected during wandering! Returning SUCCESS.")
                return pt.common.Status.SUCCESS  # Exit wander and move to detect+collect
            elif sensor_info[i] and sensor_info[i]["tag"] == "CritterMantaRay":
                print("Critter detected during wandering! Returning SUCCESS.")
                return pt.common.Status.SUCCESS  # Exit wander to avoid critter

        if not self.is_wandering:
            self.initialise()
        return pt.common.Status.RUNNING  # Keep wandering

    def terminate(self, new_status: common.Status):
        if self.wander_task and not self.wander_task.done():
            self.wander_task.cancel()
            # print("Stopped wandering")
        self.is_wandering = False

######################################### BT Collect and Run #########################################
# Tree: collect and run
class BTCollectRun:
    def __init__(self, aagent):
        self.aagent = aagent
        self.create_behavior_tree()

    def create_behavior_tree(self):
        # frozen astronaut branch
        frozen = pt.composites.Sequence(name="Sequence_frozen", memory=True)
        frozen.add_children([
            BN_DetectFrozen(self.aagent),
            BN_DoNothing(self.aagent)
        ])

        # Critter avoidance branch
        detect_critter = pt.composites.Sequence("DetectCritter", memory=True)
        detect_critter.add_children([
            BN_DetectCritter(self.aagent), 
            BN_MoveAwayFromCritter(self.aagent),  # Move away from the critter (move backward)
            BN_TurnAwayFromCritter(self.aagent),  # Turn away from the critter
            BN_LeaveCritter(self.aagent)          # Move away from the critter (move forward)
        ])

        # Inventory Full branch
        inventory_full = pt.composites.Sequence("InventoryFull", memory=True)
        inventory_full.add_children([
            BN_CheckInventoryFull(self.aagent),
            BN_GoToBase(self.aagent),
            BN_UnloadFlowers(self.aagent)
        ])

        # Detect and collect branch
        detect_and_collect = pt.composites.Sequence("DetectAndCollect", memory=True)
        detect_and_collect.add_children([
            BN_DetectFlower(self.aagent),
            BN_TurnToFlower(self.aagent),
            BN_MoveToFlower(self.aagent),
            BN_CollectFlower(self.aagent)
        ])

        # Wander branch - runs when nothing else to do
        wander = pt.composites.Sequence("Wander", memory=True)
        wander.add_children([BN_Wander(self.aagent)])

        # Root selector 
        self.root = pt.composites.Selector("BTCollectRun", memory=True)
        self.root.add_children([
            frozen,           # Highest priority
            detect_critter,     
            inventory_full,    
            detect_and_collect,
            wander            # Lowest priority
        ])

        self.behaviour_tree = pt.trees.BehaviourTree(self.root)

    async def tick(self):
        try:
            self.behaviour_tree.tick()
            await asyncio.sleep(0.1)  # Small delay to prevent CPU overload
        except Exception as e:
            print(f"Error in behavior tree tick: {e}")
            raise

    def stop_behaviour_tree(self):
        def set_invalid(node):
            node.status = pt.common.Status.INVALID
            for child in node.children:
                set_invalid(child)
        set_invalid(self.root)