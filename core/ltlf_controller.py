import re
from itertools import combinations
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from dd.autoref import BDD
import networkx as nx

from ltlf2dfa.parser.ltlf import LTLfParser

from parser.config.config_parser import load_formula_from_file


INIT_RE = re.compile(r"^\s*init\s*->\s*(\S+)\s*;\s*$")
DOUBLECIRCLE_RE = re.compile(r"^\s*node\s+\[shape\s*=\s*doublecircle\];\s*(.*)$")
EDGE_RE = re.compile(r'^\s*(\S+)\s*->\s*(\S+)\s*\[label="(.*)"\]\s*;\s*$')


def _humanize_label(label: str) -> str:
    """Replace symbolic operators with logic symbols for DOT labels."""
    label = label.replace("~", "¬")
    label = label.replace(" & ", " ∧ ")
    label = label.replace(" | ", " ∨ ")
    return label


class LTLfController:
    def __init__(
        self,
        config_file: Optional[str] = None,
        graphml_file: Optional[str] = None,
        action_vars: Optional[List[str]] = None,
        sensor_vars: Optional[List[str]] = None,
        aggressive_pruning: bool = False,
        prune: bool = True
    ) -> None:
        formula_str = ""
        if config_file is not None and graphml_file is not None:
            raise ValueError("Pass either config_file or graphml_file, not both.")

        if config_file is None and graphml_file is None:
            raise ValueError("Pass config_file, or pass graphml_file with action_vars and sensor_vars.")

        if config_file is not None:
            formula_str, sensor_vars, action_vars = load_formula_from_file(config_file)
        else:
            if action_vars is None or sensor_vars is None:
                raise ValueError("action_vars and sensor_vars are required when graphml_file is used.")

        self._sensor_vars = self._normalize_var_names(sensor_vars)
        self._action_vars = self._normalize_var_names(action_vars)

        self._bdd: BDD = BDD()
        self._bdd.configure(reordering=True)
        self._bdd.declare(*self._sensor_vars, *self._action_vars)

        if graphml_file is not None:
            self._graph = self._load_graphml(graphml_file)
        else:
            self._graph = self._build_ltl_automaton(formula_str)
            if prune:
                self._prune_graph(aggressive=aggressive_pruning)

        self._current_state: str = self._graph.graph.get("initial", "")
        self._last_sensors: Dict[str, bool] = {}
        
    def get_possible_action(self, sensor_dict: Dict[str, bool]) -> List[str]:
        sensor_env = self._normalize_sensor_input(sensor_dict)
        self._last_sensors = sensor_env
        recommended_moves: Set[str] = set()


        for _, label_bdd, _label_str in self._iter_outgoing(self._current_state):
            partial_bdd = self._bdd.let(sensor_env, label_bdd)
            if partial_bdd == self._bdd.false:
                continue

            action_bdd = self._bdd.exist(self._sensor_vars, partial_bdd)
            bdd_support = self._bdd.support(action_bdd)
            action_support = []
            for action_var in self._action_vars:
                if action_var in bdd_support:
                    action_support.append(action_var)

            if not action_support:
                if action_bdd != self._bdd.false:
                    recommended_moves.add("idle")
                continue

            for size in range(len(action_support) + 1):
                for active_set in combinations(action_support, size):
                    active_dict = {}
                    for action_var in self._action_vars:
                        active_dict[action_var] = action_var in active_set

                    if self._bdd.let(active_dict, action_bdd) == self._bdd.true:
                        if active_set:
                            move = "+".join(active_set)
                        else:
                            move = "idle"

                        recommended_moves.add(move)

        sorted_moves = sorted(recommended_moves)
        return sorted_moves

    def choose_action(self, move_str: str) -> bool:
        action_dict = {}
        for action_var in self._action_vars:
            action_dict[action_var] = False

        if move_str != "idle":
            for act in move_str.split("+"):
                if act in self._action_vars:
                    action_dict[act] = True

        env = {}
        env.update(self._last_sensors)
        env.update(action_dict)

        for dst, label_bdd, _label_str in self._iter_outgoing(self._current_state):
            if self._bdd.let(env, label_bdd) == self._bdd.true:
                self._current_state = dst
                return True

        return False

    def get_graph_dot(self, acceptance_view: bool = False) -> str:
        states = list(self._graph.nodes())
        states = sorted(states, key=str)
        lines = ['digraph "" {', '  rankdir=LR', '  graph [dpi=300]', '  node [shape="circle", fixedsize=true, width=0.65, height=0.65]', '  edge [fontsize=10]']

        if not states:
            lines.append('}')
            return "\n".join(lines)

        lines.append('  init [label="", shape="point", width=0.1, height=0.1]')

        for state in states:
            attrs = [f'label="{state}"']
            if acceptance_view and self._graph.nodes[state].get("accepting", False):
                attrs.append('shape="doublecircle"')
            lines.append(f'  {state} [{", ".join(attrs)}]')

        initial = self._graph.graph.get("initial")
        if initial is not None:
            lines.append(f'  init -> {initial}')

        source_states = list(self._graph.nodes())
        source_states = sorted(source_states, key=str)
        for source_state in source_states:
            outgoing_edges = self._iter_outgoing(source_state)
            outgoing_edges = sorted(outgoing_edges, key=self._sort_outgoing_by_destination)
            for dst, _label_bdd, label in outgoing_edges:
                lines.append(f'  {source_state} -> {dst} [label="{_humanize_label(label)}"]')

        lines.append('}')
        return "\n".join(lines)

    def _bdd_to_str(self, node: Any) -> str:
        if node == self._bdd.true:
            return "true"
        if node == self._bdd.false:
            return "false"

        support_vars = [v for v in self._action_vars if v in self._bdd.support(node)]
        if not support_vars:
            support_vars = list(self._bdd.support(node))
            if not support_vars:
                return "true" if node == self._bdd.true else "false"

        clauses = []
        for assignment in self._bdd.pick_iter(node, care_vars=support_vars):
            parts = []
            for var in support_vars:
                val = assignment.get(var)
                if val is True:
                    parts.append(var)
                elif val is False:
                    parts.append(f"¬{var}")
            clauses.append(" ∧ ".join(parts))

        if not clauses:
            return "false"
        if len(clauses) == 1:
            return clauses[0]
        return " ∨ ".join(f"({c})" for c in clauses)


    def get_step_dot(self, sensor_dict: Optional[Dict[str, bool]] = None, acceptance_view: bool = False) -> str:
        curr = self._current_state
        lines = ['digraph "" {', '  rankdir=LR', '  graph [dpi=300]', '  node [shape="circle", fixedsize=true, width=0.65, height=0.65]', 'edge [fontsize=10]']

        if not curr:
            lines.append('}')
            return "\n".join(lines)

        outgoing_edges = self._iter_outgoing(curr)

        filtered_edges = []
        if sensor_dict is not None:
            sensor_env = self._normalize_sensor_input(sensor_dict)
            for dst, label_bdd, _label_str in outgoing_edges:
                partial_bdd = self._bdd.let(sensor_env, label_bdd)
                if partial_bdd == self._bdd.false:
                    continue
                new_label = self._bdd_to_str(partial_bdd)
                filtered_edges.append((dst, partial_bdd, new_label))
        else:
            for dst, label_bdd, label_str in outgoing_edges:
                filtered_edges.append((dst, label_bdd, label_str))

        filtered_edges = sorted(filtered_edges, key=self._sort_outgoing_by_destination)

        states = {curr}
        for dst, _, _ in filtered_edges:
            states.add(dst)

        sorted_states = sorted(list(states), key=str)

        lines.append('  current [label="", shape="point", width=0.1, height=0.1]')

        for state in sorted_states:
            attrs = [f'label="{state}"']
            if acceptance_view and self._graph.nodes[state].get("accepting", False):
                attrs.append('shape="doublecircle"')
            lines.append(f'  {state} [{", ".join(attrs)}]')

        lines.append(f'  current -> {curr}')

        for dst, _, label in filtered_edges:
            lines.append(f'  {curr} -> {dst} [label="{_humanize_label(label)}"]')

        lines.append('}')
        return "\n".join(lines)



    def get_sensor_vars(self) -> List[str]:
        return list(self._sensor_vars)

    def get_action_vars(self) -> List[str]:
        return list(self._action_vars)

    def get_networkx_graph(self) -> nx.MultiDiGraph:
        return self._graph.copy()

    def export_graph(self, graphml_file: str) -> None:
        graph = nx.MultiDiGraph()
        graph.graph["initial"] = self._graph.graph.get("initial", "")

        for state in self._graph.nodes():
            is_accepting = self._graph.nodes[state].get("accepting", False)
            graph.add_node(str(state), accepting=bool(is_accepting))

        for src, dst, data in self._graph.edges(data=True):
            graph.add_edge(str(src), str(dst), label_str=str(data["label_str"]))

        nx.write_graphml(graph, graphml_file)

    def _normalize_sensor_input(self, sensor_dict: Dict[str, bool]) -> Dict[str, bool]:
        normalized_sensors = {}
        for sensor_var in self._sensor_vars:
            normalized_sensors[sensor_var] = bool(sensor_dict.get(sensor_var, False))

        return normalized_sensors

    def _normalize_var_names(self, var_names: Optional[List[str]]) -> List[str]:
        normalized_names = []
        seen_names = set()

        if var_names is None:
            return normalized_names

        for var_name in var_names:
            if var_name.lower() == "last":
                continue
            if var_name in seen_names:
                continue

            seen_names.add(var_name)
            normalized_names.append(var_name)

        return normalized_names

    def _sort_outgoing_by_destination(self, outgoing_item: Any) -> str:
        destination = outgoing_item[0]
        return str(destination)

    def _load_graphml(self, graphml_file: str) -> nx.MultiDiGraph:
        graph_path = Path(graphml_file)
        if not graph_path.exists():
            raise FileNotFoundError(f"GraphML file not found: {graphml_file}")

        loaded_graph = nx.read_graphml(graph_path)
        graph = nx.MultiDiGraph()

        accepting_states = set()
        for state, data in loaded_graph.nodes(data=True):
            state_name = str(state)
            is_accepting = self._read_bool(data.get("accepting", False))
            graph.add_node(state_name, accepting=is_accepting)

            if is_accepting:
                accepting_states.add(state_name)

        for src, dst, data in loaded_graph.edges(data=True):
            label = str(data["label_str"])
            graph.add_edge(str(src), str(dst), label_str=label, label_bdd=self._label_to_bdd(label))

        if "initial" not in loaded_graph.graph:
            raise ValueError(f"GraphML file does not define an initial state: {graphml_file}")

        initial = str(loaded_graph.graph["initial"])
        if initial not in graph:
            raise ValueError(f"GraphML initial state '{initial}' is not present in the graph.")

        graph.graph["initial"] = initial
        graph.graph["accepting_states"] = accepting_states
        return graph

    def _read_bool(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            cleaned_value = value.strip().lower()
            if cleaned_value == "true":
                return True
            if cleaned_value == "1":
                return True
            if cleaned_value == "yes":
                return True
            return False

        return bool(value)

    def _prune_graph(self, aggressive: bool = False):
        kept_states: Set[str] = set(self._graph.nodes())
        if not kept_states:
            return

        sink_states = set()
        for state in kept_states:
            if self._graph.nodes[state].get("accepting", False):
                continue
            outgoing = self._iter_outgoing(state)
            if not outgoing:
                continue
            is_sink_state = True
            for dst, label_bdd, _label_str in outgoing:
                is_self_loop = dst == state
                is_true_label = label_bdd == self._bdd.true
                if not is_self_loop or not is_true_label:
                    is_sink_state = False
                    break

            if is_sink_state:
                sink_states.add(state)

        kept_states.difference_update(sink_states)

        if aggressive:
            kept_states = self._prune_graph_aggressive(kept_states)

        initial = self._graph.graph.get("initial")
        if initial is not None and initial in kept_states:
            reachable = nx.descendants(self._graph, initial)
            reachable.add(initial)
            kept_states.intersection_update(reachable)

        self._graph = self._graph.subgraph(kept_states).copy()
        # preserve initial metadata
        self._graph.graph.setdefault("initial", initial)
        # transitions are derived from the graph when needed

    def _prune_graph_aggressive(self, kept_states: Set[str]) -> Set[str]:
        while True:
            removable_states: Set[str] = set()

            for state in kept_states:
                outgoing = self._iter_outgoing(state)
                cover = self._bdd.false

                for dst, label_bdd, _label_str in outgoing:
                    if dst not in kept_states:
                        continue

                    if self._action_vars:
                        label_bdd = self._bdd.exist(self._action_vars, label_bdd)

                    cover = self._bdd.apply("or", cover, label_bdd)

                if cover != self._bdd.true:
                    removable_states.add(state)

            if not removable_states:
                return kept_states

            kept_states = set(kept_states)
            kept_states.difference_update(removable_states)

    def _iter_outgoing(self, source_state: str) -> List[Any]:
        outgoing: List[Any] = []
        for dst in self._graph.successors(source_state):
            edge_map = self._graph.get_edge_data(source_state, dst, default={})
            if not isinstance(edge_map, dict):
                continue

            for data in edge_map.values():
                if not isinstance(data, dict):
                    continue

                label_bdd = data.get("label_bdd")
                label_str = data.get("label_str")
                if label_bdd is None or label_str is None:
                    continue

                outgoing.append((str(dst), label_bdd, str(label_str)))

        return outgoing

    def _label_to_bdd(self, label: str) -> Any:
        normalized = label.strip()
        if normalized in {"true", "1"}:
            return self._bdd.true
        if normalized in {"false", "0"}:
            return self._bdd.false
        try:
            return self._bdd.add_expr(normalized.replace("~", "!"))
        except Exception as e:
            raise ValueError(f"Failed to convert label to BDD: '{label}': {e}") from e

    def _build_ltl_automaton(self, formula_str: str):
        try:
            formula = LTLfParser()(formula_str)
            dot_source = formula.to_dfa()
        except Exception as e:
            raise RuntimeError(f"Failed to build LTL automaton from formula: {e}\nformula: {formula_str}") from e

        graph = nx.MultiDiGraph()
        accepting_states: Set[str] = set()
        init: Optional[str] = None

        for raw_line in dot_source.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("digraph") or line in {"{", "}"}:
                continue

            init_match = INIT_RE.match(line)
            if init_match:
                init = init_match.group(1)
                graph.add_node(init)
                continue

            doublecircle_match = DOUBLECIRCLE_RE.match(line)
            if doublecircle_match:
                for state in doublecircle_match.group(1).split(";"):
                    state = state.strip()
                    if state:
                        accepting_states.add(state)
                        graph.add_node(state, accepting=True)
                continue

            edge_match = EDGE_RE.match(line)
            if edge_match:
                src, dst, label = edge_match.groups()
                graph.add_node(src, accepting=src in accepting_states)
                graph.add_node(dst, accepting=dst in accepting_states)
                try:
                    label_bdd = self._label_to_bdd(label)
                except Exception as e:
                    raise ValueError(f"Error processing edge {src} -> {dst} with label '{label}': {e}") from e

                graph.add_edge(
                    src,
                    dst,
                    label_bdd=label_bdd,
                    label_str=label,
                )

        for state in graph.nodes():
            graph.nodes[state]["accepting"] = state in accepting_states

        if init is None:
            raise ValueError("Roma1 ltlf2dfa did not produce an initial state.")

        if init not in graph:
            graph.add_node(init, accepting=init in accepting_states)

        graph.graph["initial"] = init
        graph.graph["accepting_states"] = accepting_states

        return graph
