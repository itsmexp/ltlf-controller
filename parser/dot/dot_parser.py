from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set
import ast
import re

from lark import Lark, Transformer, UnexpectedInput

GRAMMAR_PATH = Path(__file__).with_name("dot_grammar.lark")
DOT_GRAMMAR = GRAMMAR_PATH.read_text(encoding="utf-8")
DOT_PARSER = Lark(DOT_GRAMMAR, start="start", parser="lalr")


@dataclass
class DotEdge:
    src: str
    dst: str
    attrs: Dict[str, str]


@dataclass
class DotNode:
    node_id: str
    attrs: Dict[str, str]


@dataclass
class DotModel:
    name: str
    assignments: Dict[str, str]
    init_target: Optional[str]
    nodes: Dict[str, DotNode]
    edges: List[DotEdge]
    accepting_nodes: Set[str]


_ATTR_RE = re.compile(r'([A-Za-z_][A-Za-z0-9_]*)\s*=\s*("(?:[^"\\]|\\.)*"|[A-Za-z_][A-Za-z0-9_]*|[0-9]+)')


def _unquote(value: str) -> str:
    value = value.strip()
    if value.startswith('"') and value.endswith('"'):
        return ast.literal_eval(value)
    return value


def _parse_attrs(raw: str) -> Dict[str, str]:
    attrs: Dict[str, str] = {}
    for key, value in _ATTR_RE.findall(raw):
        attrs[key] = _unquote(value)
    return attrs


class DotTransformer(Transformer):
    def STRING(self, token):
        return str(token)

    def GRAPH_NAME(self, token):
        return str(token)

    def ID(self, token):
        return str(token)

    def value(self, items):
        return _unquote(str(items[0]))

    def NUMBER(self, token):
        return str(token)

    def attr(self, items):
        return str(items[0]), str(items[1])

    def attr_list(self, items):
        return dict(items)

    def assignment(self, items):
        return ("assignment", str(items[0]), str(items[1]))

    def init_edge(self, items):
        raw = str(items[0]).rstrip(";")
        _, target = raw.split("->", 1)
        return ("init_edge", target.strip())

    def edge(self, items):
        src = str(items[0])
        dst = str(items[1])
        attrs = items[2] if len(items) > 2 else {}
        return ("edge", src, dst, attrs)

    def node(self, items):
        node_id = str(items[0])
        attrs = items[1] if len(items) > 1 else {}
        return ("node", node_id, attrs)

    def default_node_stmt(self, items):
        attrs = next((item for item in items if isinstance(item, dict)), {})
        return ("default_node_stmt", attrs)

    def default_edge_stmt(self, items):
        attrs = next((item for item in items if isinstance(item, dict)), {})
        return ("default_edge_stmt", attrs)

    def stmt(self, items):
        return items[0]

    def start(self, items):
        graph_name = str(items[0])
        assignments: Dict[str, str] = {}
        init_target = None
        nodes: Dict[str, DotNode] = {}
        edges: List[DotEdge] = []
        accepting_nodes: Set[str] = set()
        default_node_attrs: Dict[str, str] = {}
        default_edge_attrs: Dict[str, str] = {}

        for item in items[1:]:
            kind = item[0]
            if kind == "assignment":
                _, key, value = item
                assignments[key] = value
            elif kind == "init_edge":
                _, target = item
                init_target = target
            elif kind == "default_node_stmt":
                _, attrs = item
                default_node_attrs = attrs
            elif kind == "default_edge_stmt":
                _, attrs = item
                default_edge_attrs = attrs
            elif kind == "node":
                _, node_id, attrs = item
                merged_attrs = {**default_node_attrs, **attrs}
                if merged_attrs.get("shape") == "doublecircle":
                    accepting_nodes.add(node_id)
                nodes[node_id] = DotNode(node_id=node_id, attrs=merged_attrs)
            elif kind == "edge":
                _, src, dst, attrs = item
                merged_attrs = {**default_edge_attrs, **attrs}
                edges.append(DotEdge(src=src, dst=dst, attrs=merged_attrs))

        # Calcola l'ordine canonico dei nodi (utile per mantenere coerenza
        # di rinominazione tra grafi full/reduced/state).
        all_node_ids = set(nodes.keys())
        if init_target:
            all_node_ids.add(init_target)
        for e in edges:
            if e.src != "init":
                all_node_ids.add(e.src)
            if e.dst != "init":
                all_node_ids.add(e.dst)

        if all_node_ids:
            assignments = dict(assignments)
            assignments["canonical_node_order"] = ",".join(sorted(all_node_ids))

        return DotModel(
            name=graph_name,
            assignments=assignments,
            init_target=init_target,
            nodes=nodes,
            edges=edges,
            accepting_nodes=accepting_nodes,
        )


def parse_dot(dot_source: str) -> DotModel:
    try:
        parse_tree = DOT_PARSER.parse(dot_source)
    except UnexpectedInput as exc:
        raise ValueError(
            f"Invalid DOT format at line {exc.line}, column {exc.column}."
        ) from exc

    return DotTransformer().transform(parse_tree)


def prune_dot_model(model: DotModel) -> DotModel:
    accepting_states = set(model.accepting_nodes) | {
        node_id
        for node_id, node in model.nodes.items()
        if node.attrs.get("shape") == "doublecircle"
        or "doublecircle" in node.attrs.get("shape", "")
    }

    edges = [(edge.src, edge.dst) for edge in model.edges]
    all_nodes = set(model.nodes.keys())
    for edge in model.edges:
        if edge.src != "init":
            all_nodes.add(edge.src)
        if edge.dst != "init":
            all_nodes.add(edge.dst)

    reverse_graph: Dict[str, set] = {node: set() for node in all_nodes}
    for src, dst in edges:
        if src != "init" and dst in reverse_graph:
            reverse_graph[dst].add(src)

    good_states = set(accepting_states)
    queue = list(accepting_states)
    while queue:
        curr = queue.pop(0)
        for neighbor in reverse_graph.get(curr, set()):
            if neighbor not in good_states:
                good_states.add(neighbor)
                queue.append(neighbor)

    if model.init_target:
        good_states.add("init")
        if model.init_target in good_states:
            good_states.add(model.init_target)

    pruned_nodes = {
        node_id: node
        for node_id, node in model.nodes.items()
        if node_id in good_states
    }
    pruned_edges = [
        edge
        for edge in model.edges
        if edge.src in good_states and edge.dst in good_states
    ]

    return DotModel(
        name=model.name,
        assignments=dict(model.assignments),
        init_target=model.init_target if model.init_target in good_states else None,
        nodes=pruned_nodes,
        edges=pruned_edges,
        accepting_nodes=set(),  # Non è più necessario mantenere questa informazione dopo il pruning
    )


def _format_attr_value(value: str) -> str:
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value) or re.fullmatch(r"[0-9]+", value):
        return value
    return '"' + value.replace('"', '\\"') + '"'


def render_dot_model(model: DotModel) -> str:
    lines = [f"digraph {model.name} {{"]

    for key, value in model.assignments.items():
        lines.append(f"  {key} = {_format_attr_value(value)};")

    if model.init_target:
        lines.append('  init [shape=point, label="", width=0.01, height=0.01];')
        lines.append(f"  init -> {model.init_target};")

    for node_id, node in model.nodes.items():
        if node.attrs:
            attrs = ", ".join(
                f"{key}={_format_attr_value(value)}" for key, value in node.attrs.items()
            )
            lines.append(f"  {node_id} [{attrs}];")
        else:
            lines.append(f"  {node_id};")

    for edge in model.edges:
        if edge.attrs:
            attrs = ", ".join(
                f"{key}={_format_attr_value(value)}" for key, value in edge.attrs.items()
            )
            lines.append(f"  {edge.src} -> {edge.dst} [{attrs}];")
        else:
            lines.append(f"  {edge.src} -> {edge.dst};")

    lines.append("}")
    return "\n".join(lines)
