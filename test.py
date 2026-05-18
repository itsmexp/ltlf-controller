from ltlf2dfa.parser.ltlf import LTLfParser
from parser.dot.dot_parser import parse_dot, prune_dot_model, render_dot_model
from utils.graph_exporter import export_graph_to_png

def generate_png_from_formula(formula_str: str, output_filename: str = "automa"):
    print(f"Analisi della formula: {formula_str}")
    
    # 1. Parsing dell'LTLf a DFA
    parser = LTLfParser()
    dfa_dot = parser(formula_str).to_dfa()

    # 2. Lettura del modello DOT (senza pruning, così abbiamo l'automa base)
    dot_model = parse_dot(dfa_dot)
    
    # 2.5. Pruning (riduzione) dell'automa e stampa
    pruned_model = prune_dot_model(dot_model)
    pruned_dot_str = render_dot_model(pruned_model)
    print("Automa ridotto:\n" + pruned_dot_str)
    
    # 3. Esporta il grafo tramite la utility (applica stile grafico e PNG)
    png_path = export_graph_to_png(pruned_model, output_filename)
    
    print(f"Automa salvato in: {png_path}")

if __name__ == "__main__":
    # INSERISCI QUI LA TUA FORMULA
    formula = "G(request -> F response) & request"
    
    generate_png_from_formula(formula)
