import time
import random
from core.ltlf_controller import LTLfController
from parser.config.config_parser import load_formula_from_file

def benchmark_case(name, config_file, num_steps=1000, sensor_vars=None):
    print(f"=== Benchmarking {name} ===")
    
    # 1. File -> Formula
    t0 = time.perf_counter()
    formula_str, extracted_sensor_vars, action_vars = load_formula_from_file(config_file)
    t1 = time.perf_counter()
    time_file_to_formula = t1 - t0
    
    # 2. Formula -> Automaton
    # We must instantiate the controller but bypass its __init__ logic to time individually,
    # or just time the whole __init__ by wrapping the LTLfController class or modifying it temporarily.
    # Instead, we can just run the initialization twice or instantiate a dummy controller to use its methods.
    
    # Let's instantiate a controller without building the graph to access its methods
    controller = LTLfController.__new__(LTLfController)
    controller._sensor_vars = controller._normalize_var_names(extracted_sensor_vars)
    controller._action_vars = controller._normalize_var_names(action_vars)
    from dd.autoref import BDD
    controller._bdd = BDD()
    controller._bdd.configure(reordering=True)
    controller._bdd.declare(*controller._sensor_vars, *controller._action_vars)

    t2 = time.perf_counter()
    graph = controller._build_ltl_automaton(formula_str)
    t3 = time.perf_counter()
    time_formula_to_automaton = t3 - t2
    
    # 3. Automaton -> Pruning
    controller._graph = graph
    t4 = time.perf_counter()
    controller._prune_graph(aggressive=False)
    t5 = time.perf_counter()
    time_pruning = t5 - t4
    
    # Finish setup for action testing
    controller._current_state = controller._graph.graph.get("initial", "")
    controller._last_sensors = {}
    
    # 4. Action given sensor
    action_times = []
    
    for _ in range(num_steps):
        # Generate random sensors
        sensor_dict = {}
        for sv in controller._sensor_vars:
            sensor_dict[sv] = random.choice([True, False])
            
        t_action_start = time.perf_counter()
        possible_actions = controller.get_possible_action(sensor_dict)
        if possible_actions:
            chosen = random.choice(possible_actions)
        else:
            chosen = "idle"
        controller.choose_action(chosen)
        t_action_end = time.perf_counter()
        
        action_times.append(t_action_end - t_action_start)
        
    avg_action_time = sum(action_times) / len(action_times)
    
    print(f"Time (Input -> Formula): {time_file_to_formula*1000:.4f} ms")
    print(f"Time (Formula -> Automaton): {time_formula_to_automaton*1000:.4f} ms")
    print(f"Time (Automaton -> Pruning): {time_pruning*1000:.4f} ms")
    print(f"Average Time (Action logic): {avg_action_time*1000:.4f} ms (over {num_steps} steps)")
    print()

if __name__ == "__main__":
    benchmark_case("Patrolling Guard", "case/guard.txt")
    benchmark_case("Traffic Light (Semaphore)", "case/semaphore.txt")
