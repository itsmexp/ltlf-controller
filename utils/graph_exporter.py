from typing import Any, Dict, Set
import os
import graphviz

from parser.dot.dot_parser import DotEdge, DotModel, DotNode, render_dot_model


STANDARD_GRAPH_ASSIGNMENTS = {
    "bgcolor": "transparent",
    "margin": "0",
    "nodesep": "0.6",
    "ranksep": "0.8",
    "rankdir": "LR",
    "overlap": "false",
    "splines": "spline",
    "dpi": "300",
}

STANDARD_NODE_ATTRS = {
    "shape": "circle",
    "fixedsize": "true",
    "width": "0.6",
    "height": "0.6",
    "fontsize": "8",
    "fontname": "monospace"
}

STANDARD_EDGE_ATTRS = {
    "arrowhead": "vee",
    "arrowsize": "0.8",
    "fontname": "monospace",
    "fontsize": "8",
}


def _apply_standard_graph_style(model: DotModel) -> DotModel:
    for key, value in STANDARD_GRAPH_ASSIGNMENTS.items():
        model.assignments[key] = value
    return model

def format_and_rename_model(model: DotModel) -> DotModel:
    """
    Formatta e rinomina gli stati di un automa (DotModel).
    Assicura che tutti i nodi inizino con 'q', abbiano dimensione perfettamente
    circolare e font ridotto. I nodi di accettazione avranno il doppio cerchio.
    """
    import copy
    model = copy.deepcopy(model)
    
    name_map = {}
    current_idx = 1

    # Se il modello contiene una lista canonica di nodi (es. dal modello full),
    # usala per assegnare gli indici in modo coerente tra full/reduced/state.
    canonical = None
    if model.assignments and "canonical_node_order" in model.assignments:
        canonical = [n for n in model.assignments["canonical_node_order"].split(",") if n]
    
    # 1. Raccogli tutti i nodi possibili (da nodes, edges e init_target)
    all_node_ids = set(model.nodes.keys())
    if model.init_target:
        all_node_ids.add(model.init_target)
    for edge in model.edges:
        if edge.src != "init":
            all_node_ids.add(edge.src)
        if edge.dst != "init":
            all_node_ids.add(edge.dst)
            
    # L'iniziale è sempre q0
    if model.init_target:
        name_map[model.init_target] = "q0"

    # Se abbiamo un ordine canonico, assegniamo q1,q2... seguendo quell'ordine
    if canonical:
        for node_id in canonical:
            if node_id not in name_map and node_id != "init":
                name_map[node_id] = f"q{current_idx}"
                current_idx += 1

    # Assegna qN agli altri stati (quelli non presenti nell'ordine canonico)
    for node_id in sorted(list(all_node_ids)):
        if node_id not in name_map and node_id != "init":
            name_map[node_id] = f"q{current_idx}"
            current_idx += 1
            
    new_nodes = {}
    
    # Processa tutti i nodi trovati
    for old_id in all_node_ids:
        if old_id == "init":
            if old_id in model.nodes:
                new_nodes[old_id] = model.nodes[old_id]
            continue

        new_id = name_map.get(old_id, old_id)
        
        # Recupera il nodo originale se esiste, altrimenti crea uno fittizio
        if old_id in model.nodes:
            node = model.nodes[old_id]
            new_attrs = dict(node.attrs)
        else:
            node = DotNode(node_id=old_id, attrs={})
            new_attrs = {}
        
        # Gli stati di accettazione hanno il doppio cerchio
        is_accepting = (old_id in model.accepting_nodes) or new_attrs.get("shape") == "doublecircle"
        
        new_attrs.update(STANDARD_NODE_ATTRS)
        new_attrs["shape"] = "doublecircle" if is_accepting else "circle"
        new_attrs["label"] = new_id  
        
        node.node_id = new_id
        node.attrs = new_attrs
        new_nodes[new_id] = node
        
    model.nodes = new_nodes
    
    if model.init_target in name_map:
        model.init_target = name_map[model.init_target]
        
    for edge in model.edges:
        if edge.src in name_map:
            edge.src = name_map[edge.src]
        if edge.dst in name_map:
            edge.dst = name_map[edge.dst]
        # Sostituisce la notazione logica
        if "label" in edge.attrs:
            edge.attrs["label"] = edge.attrs["label"].replace("&", "∧").replace("|", "∨").replace("~", "¬")
        edge.attrs.update(STANDARD_EDGE_ATTRS)
            
    model.accepting_nodes = {name_map.get(n, n) for n in model.accepting_nodes}

    return _apply_standard_graph_style(model)

def export_graph_to_pdf(model: DotModel, output_filename: str = "automa") -> str:
    """
    Formatta il DotModel e lo esporta in PDF (vector) usando graphviz.
    Salva il file dentro la cartella `output/` e ritorna il percorso PDF.
    """
    formatted_model = format_and_rename_model(model)
    formatted_dot_str = render_dot_model(formatted_model)

    # Ensure output directory exists
    out_dir = "output"
    os.makedirs(out_dir, exist_ok=True)

    # Use a path inside the output directory for rendering
    out_base = os.path.join(out_dir, output_filename)
    src = graphviz.Source(formatted_dot_str)

    # Render PDF only (vector format)
    try:
        src.render(out_base, format="pdf", cleanup=True)
    except Exception as exc:
        # Bubble up error so caller can handle it if needed
        raise

    pdf_path = f"{out_base}.pdf"
    return pdf_path


def _action_label_from_assignment(action_dict: Dict[str, bool]) -> str:
    parts = []
    for act, val in sorted(action_dict.items()):
        parts.append(act if val else f"¬{act}")
    if not parts:
        return "true"
    return f"({' & '.join(parts)})"


def build_controller_state_model(controller: Any, sensor_dict: Dict[str, bool]) -> DotModel:
    """
    Builds a local graph centered on the controller current state.
    Sensor variables are fixed by sensor_dict, while the labels only enumerate
    the action-variable assignments that keep each transition feasible.
    """
    current_state = controller.current_state
    if current_state is None:
        raise ValueError("Controller has no current state to export.")

    grouped_labels: Dict[str, Set[str]] = controller.visible_transitions(sensor_dict)

    edges = []
    for dst in sorted(grouped_labels.keys()):
        labels = sorted(grouped_labels[dst])
        label = labels[0] if len(labels) == 1 else f"{' ∨ '.join(labels)}"
        edges.append(
            DotEdge(
                src=current_state,
                dst=dst,
                attrs={"label": label},
            )
        )

    node_ids = {current_state, *grouped_labels.keys()}
    nodes = {}
    for node_id in node_ids:
        nodes[node_id] = DotNode(
            node_id=node_id,
            attrs={**STANDARD_NODE_ATTRS, "label": node_id},
        )

    # Aggiungiamo un ordine canonico basato sugli stati del controller per
    # mantenere la rinominazione coerente con l'automa completo.
    canonical_nodes = sorted(set(controller.all_states) | node_ids)
    assignments = {"canonical_node_order": ",".join(canonical_nodes)}

    return DotModel(
        name="controller_state",
        assignments=assignments,
        init_target=current_state,
        nodes=nodes,
        edges=edges,
        accepting_nodes=set(),
    )


def _normalize_sensor_dict(sensor_dict: Dict[str, bool]) -> Dict[str, bool]:
    normalized = dict(sensor_dict)
    normalized.setdefault("end", False)
    return normalized


def export_controller_state_to_pdf(
    controller: Any,
    sensor_dict: Dict[str, bool],
    output_filename: str = "controller_state",
) -> str:
    """
    Exports the current controller state and all feasible outgoing transitions
    under the provided sensor assignment into a PDF saved in `output/`.
    """
    model = build_controller_state_model(controller, sensor_dict)
    return export_graph_to_pdf(model, output_filename)
