from typing import Any, Dict, Iterable
import os

import graphviz


STANDARD_GRAPH_ATTRS = {
    "bgcolor": "transparent",
    "margin": "0",
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
    "fontname": "monospace",
}

STANDARD_EDGE_ATTRS = {
    "arrowhead": "vee",
    "arrowsize": "0.8",
    "fontname": "monospace",
    "fontsize": "8",
}


def _quote(value: str) -> str:
    return '"' + value.replace('"', '\\"') + '"'


def _format_attrs(attrs: Dict[str, str]) -> str:
    return ", ".join(f"{key}={_quote(value)}" for key, value in attrs.items())


def export_graph_to_pdf(dot_source: str, output_filename: str = "automa") -> str:
    out_dir = "output"
    os.makedirs(out_dir, exist_ok=True)
    out_base = os.path.join(out_dir, output_filename)
    graphviz.Source(dot_source).render(out_base, format="pdf", cleanup=True)
    return f"{out_base}.pdf"


def _state_dot_name(state: str) -> str:
    return f"q_{state}" if not state.startswith("q_") else state


def _escape_label(label: str) -> str:
    return label.replace("\n", " ")


def build_controller_state_dot(controller: Any, sensor_dict: Dict[str, bool]) -> str:
    current_state = controller.current_state
    if current_state is None:
        raise ValueError("Controller has no current state to export.")

    grouped_labels: Dict[str, Iterable[str]] = controller.visible_transitions(sensor_dict)
    lines = ["digraph controller_state {"]

    for key, value in STANDARD_GRAPH_ATTRS.items():
        lines.append(f"  {key} = {_quote(value)};")

    lines.append(f"  node [{_format_attrs(STANDARD_NODE_ATTRS)}];")
    lines.append(f"  edge [{_format_attrs(STANDARD_EDGE_ATTRS)}];")
    lines.append('  init [shape=point, label="", width=0.01, height=0.01];')
    lines.append(f"  init -> {_state_dot_name(str(current_state))};")

    states = {str(current_state), *map(str, grouped_labels.keys())}
    for state in sorted(states):
        attrs = dict(STANDARD_NODE_ATTRS)
        attrs["label"] = state
        if state == str(current_state):
            attrs["shape"] = "doublecircle"
        lines.append(f"  {_state_dot_name(state)} [{_format_attrs(attrs)}];")

    for dst in sorted(grouped_labels.keys(), key=str):
        labels = sorted(grouped_labels[dst])
        label = labels[0] if len(labels) == 1 else " ∨ ".join(labels)
        lines.append(
            f"  {_state_dot_name(str(current_state))} -> {_state_dot_name(str(dst))} [{_format_attrs({'label': _escape_label(label)})}];"
        )

    lines.append("}")
    return "\n".join(lines)


def export_controller_state_to_pdf(
    controller: Any,
    sensor_dict: Dict[str, bool],
    output_filename: str = "controller_state",
) -> str:
    return export_graph_to_pdf(
        build_controller_state_dot(controller, sensor_dict),
        output_filename,
    )