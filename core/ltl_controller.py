import re
from itertools import combinations
from typing import Any, Dict, List, Optional, Set

from dd.autoref import BDD
import networkx as nx

from ltlf2dfa.parser.ltlf import LTLfParser

from parser.config.config_parser import load_formula_from_file


INIT_RE = re.compile(r"^\s*init\s*->\s*(\S+)\s*;\s*$")
DOUBLECIRCLE_RE = re.compile(r"^\s*node\s+\[shape\s*=\s*doublecircle\];\s*(.*)$")
EDGE_RE = re.compile(r'^\s*(\S+)\s*->\s*(\S+)\s*\[label="(.*)"\]\s*;\s*$')


class LTLController:
    def __init__(self, config_file: str) -> None:
        formula_str, sensor_vars, action_vars = load_formula_from_file(config_file)
        self._formula_str: str = formula_str

        self._sensor_vars: List[str] = [v for v in list(dict.fromkeys(sensor_vars)) if v.lower() != "last"]
        self._action_vars: List[str] = [v for v in list(dict.fromkeys(action_vars)) if v.lower() != "last"]

        self._bdd: BDD = BDD()
        self._bdd.configure(reordering=True)
        self._bdd.declare(*self._sensor_vars, *self._action_vars)

        self._graph = self._build_ltl_automaton(formula_str)
        self._current_state: str = self._graph.graph.get("initial", "")
        self._last_sensors: Dict[str, bool] = {}

        self._prune_graph()
        
    def get_possible_action(self, sensor_dict: Dict[str, bool]) -> List[str]:
        sensor_env = self._normalize_sensor_input(sensor_dict)
        self._last_sensors = sensor_env
        recommended_moves: Set[str] = set()


        for _, label_bdd, _label_str in self._iter_outgoing(self._current_state):
            partial_bdd = self._bdd.let(sensor_env, label_bdd)
            if partial_bdd == self._bdd.false:
                continue

            action_bdd = self._bdd.exist(self._sensor_vars, partial_bdd)
            action_support = [var for var in self._action_vars if var in self._bdd.support(action_bdd)]

            if not action_support:
                if action_bdd != self._bdd.false:
                    recommended_moves.add("idle")
                continue

            for size in range(len(action_support) + 1):
                for active_set in combinations(action_support, size):
                    active_dict = {var: (var in active_set) for var in self._action_vars}
                    if self._bdd.let(active_dict, action_bdd) == self._bdd.true:
                        move = "+".join(active_set) if active_set else "idle"
                        recommended_moves.add(move)

        return sorted(recommended_moves)

    def choose_action(self, move_str: str) -> bool:
        action_dict = {act: False for act in self._action_vars}
        if move_str != "idle":
            for act in move_str.split("+"):
                if act in self._action_vars:
                    action_dict[act] = True

        env = {**self._last_sensors, **action_dict}

        for dst, label_bdd, _label_str in self._iter_outgoing(self._current_state):
            if self._bdd.let(env, label_bdd) == self._bdd.true:
                self._current_state = dst
                return True

        return False

    def get_graph_dot(self) -> str:
        states = sorted(self._graph.nodes(), key=str)
        lines = ['digraph "" {', '  rankdir=LR', '  node [shape="circle"]']

        if not states:
            lines.append('}')
            return "\n".join(lines)

        lines.append('  init [label="", shape="point"]')

        for state in states:
            attrs = [f'label="{state}"']
            lines.append(f'  {state} [{", ".join(attrs)}]')

        initial = self._graph.graph.get("initial")
        if initial is not None:
            lines.append(f'  init -> {initial}')

        for source_state in sorted(self._graph.nodes(), key=str):
            for dst, _label_bdd, label in sorted(self._iter_outgoing(source_state), key=lambda item: str(item[0])):
                lines.append(f'  {source_state} -> {dst} [label="{label}"]')

        lines.append('}')
        return "\n".join(lines)

    def get_sensor_vars(self) -> List[str]:
        return list(self._sensor_vars)

    def get_action_vars(self) -> List[str]:
        return list(self._action_vars)

    def get_networkx_graph(self) -> nx.MultiDiGraph:
        return self._graph.copy()

    def _normalize_sensor_input(self, sensor_dict: Dict[str, bool]) -> Dict[str, bool]:
        return {var: bool(sensor_dict.get(var, False)) for var in self._sensor_vars}

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
            if all(dst == state and label_bdd == self._bdd.true for dst, label_bdd, _ in outgoing):
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