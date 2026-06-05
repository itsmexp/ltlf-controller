from core.ltl_controller import LTLController
from utils .dot_to_pdf import convert_dot_to_pdf

if __name__ == "__main__":
    controller = LTLController("ltl_config.txt")
    dot_source = controller.get_graph_dot()
    with open("ltl_controller_graph.dot", "w") as f:
        f.write(dot_source)
    pdf_path = convert_dot_to_pdf(dot_source, "ltl_controller_graph.pdf")
    sensor_input = {}
    print(controller.get_action_vars())
    print(controller.get_sensor_vars())
    actions = controller.get_possible_action(sensor_input)
    print(actions)
    controller.choose_action("wait")
    sensor_input = {"player_nearby": True}
    actions = controller.get_possible_action(sensor_input)
    print(actions)