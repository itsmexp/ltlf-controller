from core.ltlf_controller import LTLfController
from utils.dot_to_pdf import convert_dot_to_png
import random
import os

if __name__ == "__main__":
    controller = LTLfController(config_file="case/semaphore.txt", aggressive_pruning=True)
    dot_graph = controller.get_graph_dot(acceptance_view=False)
    os.makedirs("out/dot", exist_ok=True)
    os.makedirs("out/png", exist_ok=True)
    with open("out/dot/semaphore_graph.dot", "w") as f_graph:
        f_graph.write(dot_graph)
    convert_dot_to_png(dot_graph, "out/png/semaphore_graph.png")
    with open("out/step_actions.txt", "w") as f_actions:
        f_actions.write("")
        for i in range(10):
            dot_step_base = controller.get_step_dot(acceptance_view=False)
            with open(f"out/dot/semaphore_graph_step_{i}.dot", "w") as f_step:
                f_step.write(dot_step_base)
            convert_dot_to_png(dot_step_base, f"out/png/semaphore_graph_step_{i}.png")
            sensor_dict = {"ew_det": random.choice([True, False]), "ns_det": random.choice([True, False])}
            dot_step_pruned = controller.get_step_dot(sensor_dict, acceptance_view=False)
            with open(f"out/dot/semaphore_graph_step_{i}_pruned.dot", "w") as f_step:
                f_step.write(dot_step_pruned)
            convert_dot_to_png(dot_step_pruned, f"out/png/semaphore_graph_step_{i}_pruned.png")
            action = random.choice(controller.get_possible_action(sensor_dict))
            f_actions.write(f"Step {i}: sensor_dict={sensor_dict}, action={action}\n")
            controller.choose_action(action)
