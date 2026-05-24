from core.ltlf_controller import LTLController, build_ltl_reduced_dot, spot_formula_to_dot_source
from parser.declare.declare_parser import declare2ltlf
from utils.graph_exporter import export_controller_state_to_pdf, export_graph_to_pdf


if __name__ == "__main__":
    formula = declare2ltlf([
        "alternate-response(patrol_a, patrol_b)",
        "alternate-precedence(wait, patrol_a)",
        "alternate-precedence(wait, patrol_b)",
        "alternate-response(patrol_b, patrol_a)",
        "G(player_nearby -> (attack U !player_nearby))", 
    ])

    export_graph_to_pdf(spot_formula_to_dot_source(formula), "automa_full")
    export_graph_to_pdf(build_ltl_reduced_dot(formula), "automa_reduced")

    controller = LTLController(
        formula,
        ["player_nearby"],
        ["patrol_a", "patrol_b", "wait", "attack"],
    )

    sensor_dict = {"player_nearby": False}
    export_controller_state_to_pdf(controller, sensor_dict, "automa_state0")

    valid_actions = controller.get_possible_action(sensor_dict)
    print(valid_actions)

    if valid_actions:
        controller.choose_action(valid_actions[0])
        export_controller_state_to_pdf(controller, sensor_dict, "automa_state1")

    sensor_dict = {"player_nearby": False}
    valid_actions = controller.get_possible_action(sensor_dict)
    print(valid_actions)
    if valid_actions:
        controller.choose_action(valid_actions[0])
        export_controller_state_to_pdf(controller, sensor_dict, "automa_state2")

    sensor_dict = {"player_nearby": True}
    valid_actions = controller.get_possible_action(sensor_dict)
    print(valid_actions)
    if valid_actions:
        controller.choose_action(valid_actions[0])
        export_controller_state_to_pdf(controller, sensor_dict, "automa_state3")

    sensor_dict = {"player_nearby": False}
    valid_actions = controller.get_possible_action(sensor_dict)
    print(valid_actions)


    controller.close()