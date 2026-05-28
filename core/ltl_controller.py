from itertools import combinations
from typing import Any, Dict, List, Optional, Set

from dd.autoref import BDD
import spot

from parser.config.config_parser import load_formula_from_file


class LTLController:
    """
    Generates an automaton from an LTL specification over a set of variables.
    Integrates BDDs for efficient logical pattern matching over possible decisions.
    """

    def __init__(self, config_file: str) -> None:
        formula_str, sensor_vars, action_vars = load_formula_from_file(config_file)

        self._formula_str: str = formula_str
        self._sensor_vars: List[str] = sensor_vars
        self._action_vars: List[str] = action_vars
        self._bdd: BDD = BDD()
        self._bdd.declare(*self._sensor_vars, *self._action_vars)

        self._initial_state, automaton_transitions, accepting_states = self._build_ltl_automaton(formula_str)
        self._states: Set[str] = set(automaton_transitions.keys())
        for edges in automaton_transitions.values():
            for dst, _ in edges:
                self._states.add(dst)
        if self._initial_state is not None:
            self._states.add(self._initial_state)
        self._accepting_states: Set[str] = set(accepting_states)
        self._transitions: Dict[str, List[Any]] = {}
        self._current_state: Optional[str] = self._initial_state
        self._last_sensors: Dict[str, bool] = {}

        for source_state, edges in automaton_transitions.items():
            for dst, label in edges:
                self._transitions.setdefault(source_state, []).append(
                    (dst, self._label_to_bdd(label), label)
                )

        self._prune_graph()

    def get_possible_action(self, sensor_dict: Dict[str, bool]) -> List[str]:
        sensor_env = self._normalize_sensor_input(sensor_dict)
        self._last_sensors = sensor_env
        recommended_moves: Set[str] = set()

        if self._current_state not in self._transitions:
            return []

        for _, label_bdd, _label_str in self._transitions[self._current_state]:
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
        if self._current_state is None:
            return False

        action_dict = {act: False for act in self._action_vars}
        if move_str != "idle":
            for act in move_str.split("+"):
                if act in self._action_vars:
                    action_dict[act] = True

        env = {**self._last_sensors, **action_dict}

        for dst, label_bdd, _label_str in self._transitions.get(self._current_state, []):
            if self._bdd.let(env, label_bdd) == self._bdd.true:
                self._current_state = dst
                return True

        self._current_state = None
        return False

    def close(self):
        self._transitions.clear()
        self._last_sensors.clear()
        self._current_state = None
        self._initial_state = None
        self._states.clear()
        self._bdd = BDD()

    def get_graph_dot(self) -> str:
        states = sorted(self._states, key=str)
        lines = ['digraph "" {', '  rankdir=LR', '  node [shape="circle"]']

        if not states:
            lines.append('}')
            return "\n".join(lines)

        lines.append('  init [label="", shape="point"]')

        for state in states:
            attrs = [f'label="{state}"']
            lines.append(f'  {state} [{", ".join(attrs)}]')

        if self._initial_state is not None:
            lines.append(f'  init -> {self._initial_state}')

        for source_state in sorted(self._transitions.keys(), key=str):
            for dst, label_bdd, label_str in self._transitions[source_state]:
                # use the original propositional formula string for labels
                label = label_str
                lines.append(f'  {source_state} -> {dst} [label="{label}"]')

        lines.append('}')
        return "\n".join(lines)

    def get_sensor_vars(self) -> List[str]:
        return list(self._sensor_vars)

    def get_action_vars(self) -> List[str]:
        return list(self._action_vars)

    def _normalize_sensor_input(self, sensor_dict: Dict[str, bool]) -> Dict[str, bool]:
        return {var: bool(sensor_dict.get(var, False)) for var in self._sensor_vars}

    def _prune_graph(self, aggressive: bool = False):
        kept_states: Set[str] = set(self._states)
        if not kept_states:
            return

        sink_states = set()
        for state in kept_states:
            if state in self._accepting_states:
                continue
            outgoing = self._transitions.get(state, [])
            if not outgoing:
                continue
            # outgoing entries are (dst, label_bdd, label_str)
            if all(dst == state and label_bdd == self._bdd.true for dst, label_bdd, _ in outgoing):
                sink_states.add(state)

        kept_states.difference_update(sink_states)

        if aggressive:
            kept_states = self._prune_graph_aggressive(kept_states)

        pruned_transitions: Dict[str, List[Any]] = {}
        for source_state, edges in self._transitions.items():
            if source_state not in kept_states:
                continue

            filtered_edges = [(dst, label_bdd, label_str) for dst, label_bdd, label_str in edges if dst in kept_states]
            if filtered_edges:
                pruned_transitions[source_state] = filtered_edges

        self._transitions = pruned_transitions
        # keep states aligned with pruned transitions
        self._states = kept_states

    def _prune_graph_aggressive(self, kept_states: Set[str]) -> Set[str]:
        while True:
            removable_states: Set[str] = set()

            for state in kept_states:
                outgoing = self._transitions.get(state, [])
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

    def _label_to_bdd(self, label: str) -> Any:
        if label in {"true", "1"}:
            return self._bdd.true
        if label in {"false", "0"}:
            return self._bdd.false
        return self._bdd.add_expr(label)

    def _build_ltl_automaton(self, formula_str: str):
        automaton = spot.translate(spot.formula(formula_str), "Buchi", "Deterministic", "SBAcc")
        init = str(automaton.get_init_state_number())
        transitions: Dict[str, List[tuple]] = {}
        for edge in automaton.edges():
            src = str(edge.src)
            dst = str(edge.dst)
            label = str(spot.bdd_to_formula(edge.cond, automaton.get_dict()))
            transitions.setdefault(src, []).append((dst, label))

        accepting_states: Set[str] = set()
        try:
            num = automaton.num_states()
            for s in range(num):
                if automaton.state_is_accepting(s):
                    accepting_states.add(str(s))
        except Exception:
            print("Warning: unable to determine accepting states from automaton, skipping dead-sink pruning")

        return init, transitions, accepting_states