import time
from datetime import timedelta
import threading
import datetime

class Doors:
    OPEN = "open"
    CLOSED = "closed"
    WAIT_TIME_IN_SECONDS = 10

    class WaitThread(threading.Thread):
        def __init__(self, doors):
            super(self.__class__, self).__init__()
            self.doors = doors
            self.start_of_wait = None

        def run(self):
            self.start_of_wait = datetime.datetime.now()
            print("Doors start time set to " + str(self.start_of_wait))
            seconds_waited = 0

            print("Waiting for passengers to alight")
            while seconds_waited < Doors.WAIT_TIME_IN_SECONDS:
                print(str(seconds_waited))
                time.sleep(1)
                seconds_waited = seconds_waited + 1

            # we are awakened!
            self.doors.close()

    def __init__(self, parent, locked_with=None, passenger_triggered=False):
        self.status = Doors.CLOSED
        self.start_of_wait = None
        self.parent = parent
        self.passenger_triggered = passenger_triggered
        if locked_with:
            self.lock_with(locked_with)

    def are_open(self):
        return self.status == Doors.OPEN

    def are_closed(self):
        return self.status == Doors.CLOSED

    def lock_with(self, other_doors):
        print(self.parent.get_name() + " doors locking with " + other_doors.parent.get_name() + " doors")
        self.other_doors = other_doors
        other_doors.other_doors = self

    def open(self):
        if not self.other_doors:
            raise Exception("Cannot open if not locked with other doors")

        print(self.parent.get_name() + " doors opening")
        self.status = Doors.OPEN
        if not self.other_doors.status == Doors.OPEN:
           self.other_doors.open()

        if self.passenger_triggered:
            self.passenger_wait_thread = Doors.WaitThread(self)
            self.passenger_wait_thread.start()

    def close(self):
        self.status = Doors.CLOSED

        if self.other_doors and not self.other_doors.status == Doors.CLOSED:
            self.other_doors.close()
        self.parent.notify_doors_closed()

class Elevator:
    UP = "up"
    DOWN = "down"
    STATIONARY = "stationary"

    ARRIVAL = "arrival"

    class ElevatorMoveThread(threading.Thread):
        def __init__(self, elevator):
            super(self.__class__, self).__init__()
            self.elevator = elevator

        def run(self):
            self.elevator.do_move()

    def __init__(self, building, floors):
        self.current_floor = floors[0]
        self.last_move_state = None
        self.current_move_state = Elevator.STATIONARY
        self.building = building
        self.doors = Doors(self, floors[0].doors, passenger_triggered=True)
        self.floor_buttons = [Button(self, f) for f in floors]

    def get_name(self):
        return "elevator"

    def move(self, direction):
        if direction not in [Elevator.UP, Elevator.DOWN] or not self.can_move():
            return

        self.current_move_state = direction

        print("Elevator starting")
        self.move_thread = Elevator.ElevatorMoveThread(self)
        self.move_thread.start()

    def do_move(self):
        direction = self.current_move_state

        self.current_floor = self.building.next_floor(direction, self.current_floor)
        print("Elevator moving to floor " + str(self.current_floor.number))
        time.sleep(2) # emulate the move

        if self.building.should_elevator_stop_at(self.current_floor):
            self.stop(direction)
        elif not self.building.allows_elevator_move(direction):
            self.building.notify_stuck()
        else:
            self.do_move()

    def audible_alert(self, alert_type):
        print("Ding!!! " + alert_type)

    def can_move(self):
        return self.current_move_state == Elevator.STATIONARY and self.doors.are_closed()

    def stop(self, direction):
        print("Elevator stopping at floor " + str(self.current_floor.number))
        self.audible_alert(Elevator.ARRIVAL)
        self.doors.lock_with(self.current_floor.doors)
        if self.current_floor.wants_elevator():
            self.doors.open()
        self.current_floor.notify_elevator_arrival(direction)
        self.last_move_state = self.current_move_state
        self.current_move_state = Elevator.STATIONARY

    def notify_doors_closed(self):
        self.building.notify_elevator_ready()

    def notify_press(self, button):
        button.floor.notify_target_floor()
        self.building.notify_press(button)

class Button():
    ON = "on"
    OFF = "off"

    def __init__(self, parent, floor):
        self.state = Button.OFF
        self.parent = parent
        self.floor = floor

    def press(self):
        print("Button for floor " + str(self.floor.number) + " pressed")
        self.state = Button.ON
        self.parent.notify_press(self)

    def disable_light(self):
        self.state = Button.OFF


class FloorConsole:
    def __init__(self, floor, has_up=True, has_down=True):
        self.floor = floor
        self.down_button = Button(self, floor) if has_down else None
        self.up_button = Button(self, floor) if has_up else None

    def notify_press(self, button):
        print("Console notified of button for floor " + str(button.floor.number) + " being pressed")

        if button == self.down_button:
            self.floor.notify_down_passenger()
        else:
            self.floor.notify_up_passenger()

        self.floor.building.notify_press(button)

    def notify_elevator_arrival(self, direction):
        if not self.up_button:
            self.down_button.disable_light()

        if not self.down_button:
            self.up_button.disable_light()

        if self.up_button and direction == Elevator.UP:
            self.up_button.disable_light()

        if self.down_button and direction == Elevator.DOWN:
            self.down_button.disable_light()

    def get_name(self):
        return "floor " + str(self.floor.number) + " console"

class Floor:
    def __init__(self, building, number, is_first=False, is_top=False):
        self.number = number
        self.console = FloorConsole(self, has_up=not is_top, has_down=not is_first)
        self.doors = Doors(self)
        self.has_up_passenger = self.has_down_passenger = self.is_target_floor = False
        self.building = building

    def notify_elevator_arrival(self, direction):
        self.console.notify_elevator_arrival(direction)
        self.is_target_floor = False
        if direction == Elevator.UP:
            self.has_up_passenger = False
        elif direction == Elevator.DOWN:
            self.has_down_passenger = False

    def notify_down_passenger(self):
        self.has_down_passenger = True

    def notify_up_passenger(self):
        self.has_up_passenger = True

    def notify_target_floor(self):
        self.is_target_floor = True

    def notify_doors_closed(self):
        """ Do Nothing """

    def wants_elevator(self):
        return self.has_up_passenger or self.has_down_passenger or self.is_target_floor

    def get_name(self):
        return "floor " + str(self.number)

class Building:
    def __init__(self, floor_count):
        self.floors = [Floor(self, i, is_first=(i == 1), is_top=(i == floor_count)) for i in range(1, floor_count+1)]
        self.elevator = Elevator(self, self.floors)

    def notify_press(self, button):
        print("Building notified of elevator button press for floor " + str(button.floor.number))
        if self.elevator.current_floor.number == button.floor.number:
            self.elevator.doors.open()
        elif self.elevator.can_move():
            print("The elevator can in fact move")
            direction = Elevator.UP if self.elevator.current_floor.number < button.floor.number else Elevator.DOWN
            self.elevator.move(direction)

    def allows_elevator_move(self, direction):
        if direction == Elevator.UP and self.elevator.current_floor.number == len(self.floors):
            return False
        elif direction == Elevator.DOWN and self.elevator.current_floor.number == 1:
            return False
        else:
            return True

    def next_floor(self, direction, current_floor):
        if direction not in [Elevator.UP, Elevator.DOWN]:
            return current_floor
        elif direction == Elevator.UP and current_floor.number == len(self.floors):
            raise Exception("Cannot move up when on top floor")
        elif direction == Elevator.DOWN and current_floor.number == 1:
            raise Exception("Cannot move down when on the first floor")
        else:
            incrementer = 1 if direction == Elevator.UP else -1
            return self.floors[current_floor.number - 1 + incrementer]

    def notify_elevator_ready(self):
        any_higher_floors_want_elevator = any([floor for floor in self.floors
                                                                 if floor.number > self.elevator.current_floor.number
                                                                 and floor.wants_elevator()])
        any_lower_floors_want_elevator = any([floor for floor in self.floors
                                                                 if floor.number < self.elevator.current_floor.number
                                                                 and floor.wants_elevator()])

        if self.elevator.last_move_state == Elevator.UP and any_higher_floors_want_elevator:
            self.elevator.move(Elevator.UP)
        elif self.elevator.last_move_state == Elevator.UP and any_lower_floors_want_elevator:
            self.elevator.move(Elevator.DOWN)
        elif self.elevator.last_move_state == Elevator.DOWN and any_lower_floors_want_elevator:
            self.elevator.move(Elevator.DOWN)
        elif self.elevator.last_move_state == Elevator.DOWN and any_higher_floors_want_elevator:
            self.elevator.move(Elevator.UP)
        elif any_higher_floors_want_elevator:
            self.elevator.move(Elevator.UP)
        elif self.elevator.current_floor.number > 1:
            self.elevator.move(Elevator.DOWN)
        else:
            print("Not moving elevator because there's nothing to do")

    def should_elevator_stop_at(self, floor):
        if self.elevator.current_move_state == Elevator.DOWN and floor.number == 1: # if we're going down stop at bottom floor
            return True
        elif not floor.wants_elevator():
            return False
        elif floor.is_target_floor:
            return True
        elif floor.has_up_passenger and self.elevator.current_move_state == Elevator.UP:
            return True
        elif floor.has_down_passenger \
            and self.elevator.current_move_state == Elevator.UP \
            and not any(f for f in self.floors if f.number > floor.number and f.wants_elevator()):
            return True
        elif floor.has_down_passenger and self.elevator.current_move_state == Elevator.DOWN:
            return True
        else:
            return False


if __name__ == '__main__':
    building = Building(10)

    building.floors[0].console.up_button.press()
    time.sleep(2)
    building.elevator.floor_buttons[3].press() # this is floor 4

    building.floors[1].console.down_button.press() # this is floor 2
