from ltlf2dfa.parser.ltlf import LTLfParser
from parser.declare.declare_parser import declare2ltlf
from parser.dot.dot_parser import parse_dot, prune_dot_model, render_dot_model
from utils.graph_exporter import export_graph_to_pdf, export_controller_state_to_pdf
from core.ltlf_controller import LTLfController


def generate_png_from_formula(formula_str: str, output_filename: str = "automa"):
    
    # 1. Parsing dell'LTLf a DFA
    parser = LTLfParser()
    dfa_dot = parser(formula_str).to_dfa()

    # 2. Lettura del modello DOT (senza pruning, così abbiamo l'automa base)
    dot_model = parse_dot(dfa_dot)
    
    # 2.5. Pruning (riduzione) dell'automa e stampa
    pruned_model = prune_dot_model(dot_model)
    
    # 3. Esporta il grafo tramite la utility (applica stile grafico e PNG)
    export_graph_to_pdf(dot_model, output_filename + "_full")
    export_graph_to_pdf(pruned_model, output_filename + "_reduced")


    

if __name__ == "__main__":
    output_filename = "automa"
    declare_formula = []
    declare_formula.append("init(spawn)")
    declare_formula.append("GF(raggiungi_a)")
    declare_formula.append("GF(raggiungi_b)")
    declare_formula.append("G!(raggiungi_a & raggiungi_b)")
    declare_formula.append("G(last -> muori)")



    
    formula = declare2ltlf(declare_formula)
    generate_png_from_formula(formula, output_filename)

    sensor_vars = ["nemico_vicino", "muori"]
    action_vars = ["raggiungi_a", "raggiungi_b", "spawn", "idle", "attacca"]
    controller = LTLfController(formula, sensor_vars, action_vars)

    sensor_dict = {"nemico_vicino": False, "muori": False}
    export_controller_state_to_pdf(controller, sensor_dict, output_filename + "_state0")
    controller.choose_action("spawn")

    sensor_dict = {"nemico_vicino": True, "muori": False}
    export_controller_state_to_pdf(controller, sensor_dict, output_filename + "_state1")
    print(controller.get_possible_action(sensor_dict))

   
