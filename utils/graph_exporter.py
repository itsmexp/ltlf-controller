import graphviz
from parser.dot.dot_parser import DotModel, render_dot_model, DotNode

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
    
    # Assegna q1, q2... agli altri stati
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
        
        new_attrs["shape"] = "doublecircle" if is_accepting else "circle"
        
        new_attrs["fixedsize"] = "true"
        new_attrs["width"] = "0.6"
        new_attrs["height"] = "0.6"
        new_attrs["label"] = new_id  # Rimosse le virgolette letterali
        new_attrs["fontsize"] = "10"
        new_attrs["fontname"] = "monospace"  # Tema monospace per i nodi
        new_attrs["style"] = "filled"        # Riempi il nodo
        new_attrs["fillcolor"] = "white"     # Colore di riempimento bianco
        
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
        # Aggiungiamo lo stile per la punta più fine e il tema monospace
        edge.attrs["arrowhead"] = "vee"
        edge.attrs["arrowsize"] = "0.8"
        edge.attrs["fontname"] = "monospace"  # Tema monospace per gli archi
            
    model.accepting_nodes = {name_map.get(n, n) for n in model.accepting_nodes}
    
    # Imposta lo sfondo trasparente a livello globale sul grafo
    model.assignments["bgcolor"] = "transparent"
    # Taglia il bordo dell'immagine al minimo
    model.assignments["margin"] = "0"
    # Aumenta la risoluzione a 300 DPI per evitare la perdita di qualità su grafi molto ampi
    model.assignments["dpi"] = "300"
    
    return model

def export_graph_to_png(model: DotModel, output_filename: str = "automa") -> str:
    """
    Formatta il DotModel e lo esporta in PNG con sfondo trasparente usando graphviz.
    Rimuove automaticamente i bordi trasparenti in eccesso.
    Ritorna il path completo del PNG generato.
    """
    formatted_model = format_and_rename_model(model)
    formatted_dot_str = render_dot_model(formatted_model)
    
    src = graphviz.Source(formatted_dot_str)
    src.render(output_filename, format="png", cleanup=True)
    
    png_path = f"{output_filename}.png"
    
    # Ritaglia l'immagine ai margini minimi rimuovendo i pixel trasparenti
    try:
        from PIL import Image
        with Image.open(png_path) as img:
            # img.getbbox() restituisce il rettangolo (left, upper, right, lower)
            # che racchiude i pixel non nulli (non trasparenti).
            bbox = img.getbbox()
            if bbox:
                cropped_img = img.crop(bbox)
                cropped_img.save(png_path)
    except ImportError:
        print("Avviso: Pillow non installato. Impossibile ritagliare i bordi in eccesso.")
        pass
        
    return png_path
