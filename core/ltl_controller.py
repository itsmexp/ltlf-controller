from itertools import combinations
from typing import Any, Dict, List, Optional, Set

from dd.autoref import BDD
import networkx as nx
import spot

from parser.config.config_parser import load_formula_from_file


class LTLController:
    def __init__(self, config_file: str) -> None:
        formula_str, sensor_vars, action_vars = load_formula_from_file(config_file)

        self._formula_str: str = formula_str
        self._sensor_vars: List[str] = sensor_vars
        self._action_vars: List[str] = action_vars
        self._bdd: BDD = BDD()
        self._bdd.declare(*self._sensor_vars, *self._action_vars)

        self._graph = self._build_ltl_automaton(formula_str)
        self._current_state: Optional[str] = self._graph.graph.get("initial")
        self._last_sensors: Dict[str, bool] = {}

        self._prune_graph()
        
    def get_possible_action(self, sensor_dict: Dict[str, bool]) -> List[str]:
        sensor_env = self._normalize_sensor_input(sensor_dict)
        self._last_sensors = sensor_env
        recommended_moves: Set[str] = set()

        current_state = self._current_state
        if current_state is None or current_state not in self._graph:
            return []

        for _, label_bdd, _label_str in self._iter_outgoing(current_state):
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
        current_state = self._current_state
        if current_state is None:
            return False

        action_dict = {act: False for act in self._action_vars}
        if move_str != "idle":
            for act in move_str.split("+"):
                if act in self._action_vars:
                    action_dict[act] = True

        last = self._last_sensors
        env = {**last, **action_dict}

        for dst, label_bdd, _label_str in self._iter_outgoing(current_state):
            if self._bdd.let(env, label_bdd) == self._bdd.true:
                self._current_state = dst
                return True

            self._current_state = None
        return False

    def close(self):
        self._graph.clear()
        self._graph = nx.MultiDiGraph()
        self._graph.graph["initial"] = None
        self._bdd = BDD()
        self._current_state = None
        self._last_sensors = {}

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
        if label in {"true", "1"}:
            return self._bdd.true
        if label in {"false", "0"}:
            return self._bdd.false
        return self._bdd.add_expr(label)

    def _build_ltl_automaton(self, formula_str: str):
        automaton = spot.translate(spot.formula(formula_str), "Buchi", "Deterministic", "SBAcc")
        init = str(automaton.get_init_state_number())
        accepting_states: Set[str] = set()

        try:
            num = automaton.num_states()
            for s in range(num):
                if automaton.state_is_accepting(s):
                    accepting_states.add(str(s))
        except Exception:
            print("Warning: unable to determine accepting states from automaton, skipping dead-sink pruning")

        graph = nx.MultiDiGraph()
        for edge in automaton.edges():
            src = str(edge.src)
            dst = str(edge.dst)
            label = str(spot.bdd_to_formula(edge.cond, automaton.get_dict()))
            graph.add_node(src, accepting=src in accepting_states)
            graph.add_node(dst, accepting=dst in accepting_states)
            graph.add_edge(
                src,
                dst,
                label_bdd=self._label_to_bdd(label),
                label_str=label,
            )

        if init is not None and init not in graph:
            graph.add_node(init, accepting=init in accepting_states)

        graph.graph["initial"] = init
        graph.graph["accepting_states"] = accepting_states

        return graph