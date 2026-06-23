from core.ltlf_controller import LTLfController
from utils.dot_to_pdf import convert_dot_to_png
import os

if __name__ == "__main__":
    controller = LTLfController(config_file="case/guard.txt", aggressive_pruning=False)
    
    os.makedirs("thesis_out", exist_ok=True)

    # Global Graph
    dot_graph = controller.get_graph_dot(acceptance_view=False, show_transition_count=True)
    convert_dot_to_png(dot_graph, "thesis_out/graph.png")

    # Mealy Machine Graph
    dot_mealy = controller.get_mealy_graph_dot(acceptance_view=False)
    with open("thesis_out/mealy_graph.dot", "w") as f:
        f.write(dot_mealy)
    convert_dot_to_png(dot_mealy, "thesis_out/mealy_graph.png")

    # Step 1 Global
    dot_step_1 = controller.get_step_dot(acceptance_view=False, show_transition_count=True)
    convert_dot_to_png(dot_step_1, "thesis_out/step_1.png")

    # Normal Patrol (no threat, full health)
    # player_nearby=False, low_hp=False
    sensor_patrol = {"in_a": False, "in_b": False, "player_nearby": False, "low_hp": False}
    dot_patrol = controller.get_step_dot(sensor_patrol, acceptance_view=False, show_transition_count=True)
    convert_dot_to_png(dot_patrol, "thesis_out/step_1_patrol_pruned.png")

    # Combat Mode (threat detected, full health)
    # player_nearby=True, low_hp=False
    sensor_combat = {"in_a": False, "in_b": False, "player_nearby": True, "low_hp": False}
    dot_combat = controller.get_step_dot(sensor_combat, acceptance_view=False, show_transition_count=True)
    convert_dot_to_png(dot_combat, "thesis_out/step_1_combat_pruned.png")

    # Flee/Heal Mode (threat detected, low health)
    # player_nearby=True, low_hp=True
    sensor_flee = {"in_a": False, "in_b": False, "player_nearby": True, "low_hp": True}
    dot_flee = controller.get_step_dot(sensor_flee, acceptance_view=False, show_transition_count=True)
    convert_dot_to_png(dot_flee, "thesis_out/step_1_flee_heal_pruned.png")
