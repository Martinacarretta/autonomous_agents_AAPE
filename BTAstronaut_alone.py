
#################################################
# 1st scenario: Astronaut Alone
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
'''

# Node: Check if inventory is full
class BN_CheckInventoryFull(pt.behaviour.Behaviour):
    def __init__(self, aagent):
        super().__init__("CheckInventoryFull")
        self.my_agent = aagent

    def update(self):
        # Check if the inventory is full (amount >= 2
        print("START OF BEHAVIOR TREE")
        # print('Checking inventory...')
        for item in self.my_agent.i_state.myInventoryList:
            # print(item["name"], item["amount"])
            if item["name"] == "AlienFlower" and item["amount"] >= 2:
                print("Inventory full")
                return pt.common.Status.SUCCESS
        return pt.common.Status.FAILURE

# Node: Go to base
class BN_GoToBase(pt.behaviour.Behaviour):
    def __init__(self, aagent):
        super().__init__("GoToBase")
        self.my_agent = aagent
        self.task = None

    def initialise(self):
        self.task = asyncio.create_task(self.my_agent.send_message("action", "walk_to,Base"))

    def update(self):
        if self.my_agent.i_state.currentNamedLoc == "Base" and self.my_agent.i_state.onRoute == False:
            print('Reached base. SUCCESS')
            return pt.common.Status.SUCCESS
        else:
            #print('running to base...')
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
            return pt.common.Status.RUNNING  # Still unloading flowers
        else:
            for item in self.my_agent.i_state.myInventoryList:
                if item["name"] == "AlienFlower":
                    print('failure unloading flowers...')# in case there are still flowers in the inventory return failure
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
                if sensor_info[i]["distance"] < min_distance:# look for the closest flower
                    min_distance = sensor_info[i]["distance"]
                    turn_angle = sensor_degree[i]# get the angle to turn to flower based on the sensor index

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
            self.new_heading = None  # Important fallback

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
            self.task = asyncio.create_task(Goals_BT.ForwardDist(self.my_agent, min_distance, 1, 100).run())
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
         
            
class BN_Wander(pt.behaviour.Behaviour):
    def __init__(self, aagent):
        super().__init__("Wander")
        self.my_agent = aagent
        self.wander_task = None
        self.is_wandering = False

    def initialise(self):
        if not self.is_wandering:
            self.wander_task = asyncio.create_task(Goals_BT.Avoid(self.my_agent).run())
            self.is_wandering = True
            # print("Started wandering")

    def update(self):
        sensor_info = self.my_agent.rc_sensor.sensor_rays[Sensors.RayCastSensor.OBJECT_INFO]
        for i in range(len(sensor_info)):
            if sensor_info[i] and sensor_info[i]["tag"] == "AlienFlower":
                print("Flower detected during wandering! Returning SUCCESS.")
                return pt.common.Status.SUCCESS  # Exit wander and move to detect+collect
        if not self.is_wandering:
            self.initialise()
        return pt.common.Status.RUNNING  # Keep wandering

    def terminate(self, new_status: common.Status):
        if self.wander_task and not self.wander_task.done():
            self.wander_task.cancel()
            # print("Stopped wandering")
        self.is_wandering = False

######################################### BT Astronaut Alone #########################################
# Tree: Astronaut Alone
class BTAstronautAlone:
    def __init__(self, aagent):
        self.aagent = aagent
        self.create_behavior_tree()

    def create_behavior_tree(self):
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

        # Root selector - order determines priority
        self.root = pt.composites.Selector("AstronautAlone", memory=True)
        self.root.add_children([
            inventory_full,    # Highest priority
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