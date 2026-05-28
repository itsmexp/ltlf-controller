from core.ltl_controller import LTLController

if __name__ == "__main__":
    controller = LTLController("example_input.txt")
    sensor_input = {}
    print(controller.get_action_vars())
    print(controller.get_sensor_vars())
    actions = controller.get_possible_action(sensor_input)
    print(actions)
    controller.choose_action("wait")
    actions = controller.get_possible_action(sensor_input)
    print(actions)
    controller.choose_action("wait")
    actions = controller.get_possible_action(sensor_input)

    


