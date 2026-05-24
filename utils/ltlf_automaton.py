from dataclasses import dataclass
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set

from dd.autoref import BDD
from ltlf2dfa.parser.ltlf import LTLfParser

from parser.dot.dot_parser import parse_dot, prune_dot_model


@dataclass(frozen=True)
class AutomatonTransition:
    src: str
    dst: str
    label: str


@dataclass
class LTLfAutomaton:
    initial_state: Optional[str]
    transitions: Dict[str, List[AutomatonTransition]]


class LTLfControllerRuntime:
    """
    Runtime layer that owns the BDD environment and transition evaluation.

    The controller delegates to this class so it does not need to know about
    BDD details or transition encoding.
    """

    def __init__(
        self,
        automaton: LTLfAutomaton,
        sensor_vars: List[str],
        action_vars: List[str],
    ):
        self.sensor_vars = sensor_vars
        self.action_vars = action_vars
        self.bdd: BDD = BDD()
        self.bdd.declare(*self.sensor_vars, *self.action_vars)

        self.transitions: Dict[str, List[Any]] = {}
        self.initial_state: Optional[str] = automaton.initial_state
        self.current_state: Optional[str] = automaton.initial_state
        self.last_sensors: Dict[str, bool] = {}

        for source_state, edges in automaton.transitions.items():
            for edge in edges:
                self.transitions.setdefault(source_state, []).append(
                    (edge.dst, self._label_to_bdd(edge.label))
                )

    @property
    def all_states(self) -> Set[str]:
        states: Set[str] = set(self.transitions.keys())
        for edges in self.transitions.values():
            for dst, _ in edges:
                states.add(dst)
        if self.current_state is not None:
            states.add(self.current_state)
        return states

    def get_possible_action(self, sensor_dict: Dict[str, bool]) -> List[str]:
        self.last_sensors = sensor_dict
        possible_moves: Set[str] = set()

        if self.current_state not in self.transitions:
            return []

        for dst, label_bdd in self.transitions[self.current_state]:
            partial_bdd = self.bdd.let(sensor_dict, label_bdd)

            if partial_bdd != self.bdd.false:
                for action_dict in self.bdd.pick_iter(partial_bdd, care_vars=self.action_vars):
                    move_name = self._parse_move_name(action_dict)
                    possible_moves.add(move_name)

        return list(possible_moves)

    def choose_action(self, move_str: str) -> bool:
        if self.current_state is None:
            return False

        action_dict = {act: False for act in self.action_vars}
        if move_str != "idle":
            for act in move_str.split("+"):
                if act in self.action_vars:
                    action_dict[act] = True

        env = {**self.last_sensors, **action_dict}

        for dst, label_bdd in self.transitions.get(self.current_state, []):
            eval_bdd = self.bdd.let(env, label_bdd)
            if eval_bdd == self.bdd.true:
                self.current_state = dst
                return True

        self.current_state = None
        return False

    def visible_transitions(self, sensor_dict: Dict[str, bool]) -> Dict[str, Set[str]]:
        if self.current_state is None:
            return {}

        grouped_labels: Dict[str, Set[str]] = defaultdict(set)
        for dst, label_bdd in self.transitions.get(self.current_state, []):
            partial_bdd = self.bdd.let(sensor_dict, label_bdd)
            if partial_bdd == self.bdd.false:
                continue

            action_found = False
            for action_dict in self.bdd.pick_iter(partial_bdd, care_vars=self.action_vars):
                grouped_labels[dst].add(self._action_label_from_assignment(action_dict))
                action_found = True

            if not action_found:
                grouped_labels[dst].add("true")

        return grouped_labels

    def close(self) -> None:
        self.transitions.clear()

    def _parse_move_name(self, action_dict: Dict[str, bool]) -> str:
        active = [act for act, val in action_dict.items() if val]
        return "+".join(active) if active else "idle"

    def _label_to_bdd(self, label: str) -> Any:
        if label == "true":
            return self.bdd.true
        if label == "false":
            return self.bdd.false

        return self.bdd.add_expr(label)

    def _action_label_from_assignment(self, action_dict: Dict[str, bool]) -> str:
        parts = []
        for act, val in sorted(action_dict.items()):
            parts.append(act if val else f"¬{act}")
        if not parts:
            return "true"
        return f"({' & '.join(parts)})"


def build_ltlf_automaton(formula_str: str) -> LTLfAutomaton:
    """
    Compiles an LTLf formula into a pruned automaton representation.

    The DOT parsing and pruning details stay hidden inside this utility so the
    controller can work with a simple transition model.
    """
    parser = LTLfParser()
    dfa_dot = parser(formula_str).to_dfa()
    dot_model = prune_dot_model(parse_dot(dfa_dot))

    transitions: Dict[str, List[AutomatonTransition]] = {}
    for edge in dot_model.edges:
        label = edge.attrs.get("label")
        if label is None:
            continue
        transitions.setdefault(edge.src, []).append(
            AutomatonTransition(src=edge.src, dst=edge.dst, label=label)
        )

    return LTLfAutomaton(initial_state=dot_model.init_target, transitions=transitions)


def build_ltlf_controller_runtime(
    formula_str: str,
    sensor_vars: List[str],
    action_vars: List[str],
) -> LTLfControllerRuntime:
    """Builds the BDD-backed runtime used by the controller."""
    automaton = build_ltlf_automaton(formula_str)
    return LTLfControllerRuntime(automaton, sensor_vars, action_vars)