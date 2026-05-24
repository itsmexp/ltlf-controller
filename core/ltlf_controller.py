from collections import defaultdict
from dataclasses import dataclass
import json
import os
import shutil
import subprocess
from typing import Any, Dict, List, Optional, Set

from dd.autoref import BDD


@dataclass(frozen=True)
class AutomatonTransition:
    src: str
    dst: str
    label: str


@dataclass
class LTLAutomaton:
    initial_state: Optional[str]
    transitions: Dict[str, List[AutomatonTransition]]


_SPOT_TRANSLATOR = (
    "import json\n"
    "import spot\n"
    "import sys\n"
    "\n"
    "formula = sys.argv[1]\n"
    "automaton = spot.translate(spot.formula(formula), \"Buchi\", \"Deterministic\", \"SBAcc\")\n"
    "data = {\n"
    "    \"initial_state\": str(automaton.get_init_state_number()),\n"
    "    \"transitions\": [\n"
    "        {\n"
    "            \"src\": str(edge.src),\n"
    "            \"dst\": str(edge.dst),\n"
    "            \"label\": str(spot.bdd_to_formula(edge.cond, automaton.get_dict())),\n"
    "        }\n"
    "        for edge in automaton.edges()\n"
    "    ],\n"
    "    \"dot\": automaton.to_str(\"dot\"),\n"
    "    \"hoa\": automaton.to_str(\"hoa\"),\n"
    "}\n"
    "print(json.dumps(data))\n"
)


def _spot_python_executable() -> str:
    candidate = os.environ.get("SPOT_PYTHON") or shutil.which("python3.12")
    if not candidate:
        raise RuntimeError("Spot backend requires Python 3.12 with python3-spot installed.")
    return candidate


def _spot_translate(formula_str: str) -> Dict[str, Any]:
    try:
        result = subprocess.run(
            [_spot_python_executable(), "-c", _SPOT_TRANSLATOR, formula_str],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else ""
        raise RuntimeError(f"Spot translation failed: {stderr or exc}") from exc

    return json.loads(result.stdout)


def spot_formula_to_dot_source(formula_str: str) -> str:
    return _spot_translate(formula_str)["dot"]


def build_ltl_automaton(formula_str: str) -> LTLAutomaton:
    data = _spot_translate(formula_str)
    transitions: Dict[str, List[AutomatonTransition]] = {}
    for edge in data["transitions"]:
        transitions.setdefault(str(edge["src"]), []).append(
            AutomatonTransition(
                src=str(edge["src"]),
                dst=str(edge["dst"]),
                label=str(edge["label"]),
            )
        )

    return LTLAutomaton(initial_state=str(data["initial_state"]), transitions=transitions)


def build_ltl_reduced_dot(formula_str: str) -> str:
    data = _spot_translate(formula_str)
    transitions = data["transitions"]

    states: Set[str] = set()
    incoming: Dict[str, Set[str]] = defaultdict(set)
    for edge in transitions:
        src = str(edge["src"])
        dst = str(edge["dst"])
        states.add(src)
        states.add(dst)
        incoming[dst].add(src)

    accepting_states: Set[str] = set()
    for raw_line in data["hoa"].splitlines() if "hoa" in data else []:
        stripped = raw_line.strip()
        if stripped.startswith("State:") and "{0}" in stripped:
            accepting_states.add(stripped.split()[1])

    if not accepting_states:
        accepting_states = set(states)

    good_states: Set[str] = set(accepting_states)
    queue: List[str] = list(accepting_states)
    while queue:
        current = queue.pop(0)
        for prev in incoming.get(current, set()):
            if prev not in good_states:
                good_states.add(prev)
                queue.append(prev)

    init_state = str(data["initial_state"])
    good_states.add(init_state)

    reduced_transitions = [
        edge for edge in transitions
        if str(edge["src"]) in good_states and str(edge["dst"]) in good_states
    ]

    lines = ["digraph reduced_automaton {"]
    lines.append('  rankdir="LR";')
    lines.append('  init [shape=point, label="", width=0.01, height=0.01];')
    lines.append(f"  init -> {init_state};")

    for state in sorted(good_states):
        shape = "doublecircle" if state in accepting_states else "circle"
        lines.append(f'  {state} [label="{state}", shape={shape}];')

    for edge in reduced_transitions:
        lines.append(
            f'  {edge["src"]} -> {edge["dst"]} [label="{str(edge["label"])}"];'
        )

    lines.append("}")
    return "\n".join(lines)


class LTLController:
    """
    Generates an automaton from an LTL specification over a set of variables.
    Integrates BDDs for efficient logical pattern matching over possible decisions.
    """

    def __init__(
        self,
        formula_str: str,
        sensor_vars: List[str],
        action_vars: List[str],
    ):
        self.formula_str: str = formula_str
        self.sensor_vars: List[str] = sensor_vars
        self.action_vars: List[str] = action_vars
        self.bdd: BDD = BDD()
        self.bdd.declare(*self.sensor_vars, *self.action_vars)

        automaton = build_ltl_automaton(formula_str)
        self.transitions: Dict[str, List[Any]] = {}
        self._initial_state: Optional[str] = automaton.initial_state
        self._current_state: Optional[str] = automaton.initial_state
        self.last_sensors: Dict[str, bool] = {}

        for source_state, edges in automaton.transitions.items():
            for edge in edges:
                self.transitions.setdefault(source_state, []).append(
                    (edge.dst, self._label_to_bdd(edge.label))
                )

    @property
    def initial_state(self) -> Optional[str]:
        return self._initial_state

    @property
    def current_state(self) -> Optional[str]:
        return self._current_state

    @property
    def all_states(self):
        states: Set[str] = set(self.transitions.keys())
        for edges in self.transitions.values():
            for dst, _ in edges:
                states.add(dst)
        if self._current_state is not None:
            states.add(self._current_state)
        return states

    def visible_transitions(self, sensor_dict: Dict[str, bool]):
        if self._current_state is None:
            return {}

        grouped_labels: Dict[str, Set[str]] = defaultdict(set)
        for dst, label_bdd in self.transitions.get(self._current_state, []):
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

    def get_possible_action(self, sensor_dict: Dict[str, bool]) -> List[str]:
        self.last_sensors = sensor_dict
        recommended_moves: Set[str] = set()
        minimal_action_sets: List[Set[str]] = []

        if self._current_state not in self.transitions:
            return []

        for _, label_bdd in self.transitions[self._current_state]:
            partial_bdd = self.bdd.let(sensor_dict, label_bdd)
            if partial_bdd == self.bdd.false:
                continue

            dependent_actions = sorted(
                set(self.action_vars).intersection(self.bdd.support(partial_bdd))
            )
            if not dependent_actions:
                continue

            for action_dict in self.bdd.pick_iter(partial_bdd, care_vars=dependent_actions):
                active_set = {act for act, val in action_dict.items() if val}
                if not active_set:
                    continue

                if any(existing.issubset(active_set) for existing in minimal_action_sets):
                    continue

                minimal_action_sets = [
                    existing for existing in minimal_action_sets if not active_set.issubset(existing)
                ]
                minimal_action_sets.append(active_set)

        for active_set in minimal_action_sets:
            move = "+".join(sorted(active_set)) if active_set else "idle"
            recommended_moves.add(move)

        return sorted(recommended_moves)

    def choose_action(self, move_str: str) -> bool:
        if self._current_state is None:
            return False

        action_dict = {act: False for act in self.action_vars}
        if move_str != "idle":
            for act in move_str.split("+"):
                if act in self.action_vars:
                    action_dict[act] = True

        env = {**self.last_sensors, **action_dict}

        for dst, label_bdd in self.transitions.get(self._current_state, []):
            if self.bdd.let(env, label_bdd) == self.bdd.true:
                self._current_state = dst
                return True

        self._current_state = None
        return False

    def close(self):
        self.transitions.clear()
        self.last_sensors.clear()
        self._current_state = None
        self._initial_state = None
        self.bdd = BDD()

    def _parse_move_name(self, action_dict: Dict[str, bool]) -> str:
        active = [act for act, val in action_dict.items() if val]
        return "+".join(active) if active else "idle"

    def _label_to_bdd(self, label: str) -> Any:
        if label in {"true", "1"}:
            return self.bdd.true
        if label in {"false", "0"}:
            return self.bdd.false
        return self.bdd.add_expr(label)

    def _action_label_from_assignment(self, action_dict: Dict[str, bool]) -> str:
        parts = []
        for act, val in sorted(action_dict.items()):
            parts.append(act if val else f"¬{act}")
        if not parts:
            return "true"
        return f"({' & '.join(parts)})"