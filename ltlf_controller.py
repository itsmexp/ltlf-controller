"""
ltlf_controller.py
------------------
Class responsible for compiling and managing behavioral patterns
through DFA conversion of LTLf expressions and partial extraction with BDDs.
"""

from typing import List, Dict, Tuple, Optional, Any, Set

from dd.autoref import BDD
from ltlf2dfa.parser.ltlf import LTLfParser

from parser.dot.dot_parser import DotModel, parse_dot, prune_dot_model, render_dot_model


class LTLfController:
    """
    Generates a DFA automaton from an LTLf specification over a set
    of variables. Integrates BDDs (Binary Decision Diagrams) for efficient
    logical pattern matching over possible decisions at each state.
    """

    def __init__(self, formula_str: str, sensor_vars: List[str], action_vars: List[str]):
        """
        Initializes the LTLf controller, generates the pruned automaton,
        and configures the BDD environment.

        :param formula_str: LTLf logic formula as a string.
        :param sensor_vars: List of variables defining world state (sensors).
        :param action_vars: List of variables defining possible actions.
        """
        self.sensor_vars: List[str] = sensor_vars
        self.action_vars: List[str] = action_vars

        # 1. Build and prune DFA
        parser = LTLfParser()
        dfa_dot: str = parser(formula_str).to_dfa()
        self.dot_model: DotModel = parse_dot(dfa_dot)
        self.pruned_dot_model: DotModel = prune_dot_model(self.dot_model)
        self.pruned_dot: str = render_dot_model(self.pruned_dot_model)

        # 2. Setup BDD environment
        self.bdd: BDD = BDD()
        self.bdd.declare(*self.sensor_vars, *self.action_vars)

        # 3. Stateful runtime variables
        self.transitions: Dict[str, List[Tuple[str, Any]]] = {}
        self.current_state: Optional[str] = None
        self.last_sensors: Dict[str, bool] = {}

        # 4. Parse DOT model in memory to build transitions
        self._parse_dot_to_graph(self.pruned_dot_model)

    def get_dot_graph(self) -> str:
        """
        Returns the pruned automaton representation in DOT format.
        """
        return self.pruned_dot

    def get_possible_action(
        self, sensor_dict: Dict[str, bool], return_dot: bool = False
    ) -> Any:
        """
        Returns feasible move combinations from the current state,
        filtered by current sensor constraints.

        :param sensor_dict: Sensor map with current values (e.g. {"s1": True}).
        :param return_dot: If True, also returns a tuple with the partial graph
                           of adjacent transitions filtered by sensors.
        :return: List of strings (e.g. ["idle", "a1"]). If return_dot is True,
                 returns (move_list, dot_string).
        """
        self.last_sensors = sensor_dict
        possible_moves: Set[str] = set()
        active_transitions: List[Tuple[str, str]] = []

        if self.current_state not in self.transitions:
            return ([], "") if return_dot else []

        for dst, label_bdd in self.transitions[self.current_state]:
            partial_bdd = self.bdd.let(sensor_dict, label_bdd)

            if partial_bdd != self.bdd.false:
                valid_formulas: List[str] = []

                # Iterate possible assignments for remaining action variables
                for action_dict in self.bdd.pick_iter(partial_bdd, care_vars=self.action_vars):
                    move_name = self._parse_move_name(action_dict)
                    possible_moves.add(move_name)

                    valid_formulas.append(self._action_dict_to_expr(action_dict))

                # Select reduced label for this edge
                reduced_label = self._generate_reduced_label(valid_formulas)
                active_transitions.append((dst, reduced_label))

        if return_dot:
            partial_dot = self._build_partial_dot(active_transitions)
            return list(possible_moves), partial_dot

        return list(possible_moves)

    def choose_action(self, move_str: str) -> bool:
        """
        Applies the chosen move to the automaton and updates internal state.

        :param move_str: Move identifier string, joined by '+' (e.g. "a1+a2" or "idle").
        :return: True if move is allowed and the node advances, False otherwise.
        """
        if self.current_state is None:
            return False

        # Rebuild action values from selected move string
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

        print(f"[Controller] Error: move '{move_str}' is not allowed or malformed in the current state!")
        self.current_state = None
        return False

    def close(self):
        """
        Force-clears internal BDD objects by deleting the transition map.
        Prevents leaking dangling nodes in memory after execution.
        """
        self.transitions.clear()

    # --- PRIVATE HELPER METHODS ---

    def _parse_move_name(self, action_dict: Dict[str, bool]) -> str:
        """
        Converts an action dictionary to a user-friendly string,
        including only True-valued actions joined by "+".
        """
        active = [act for act, val in action_dict.items() if val]
        return "+".join(active) if active else "idle"

    def _action_dict_to_expr(self, action_dict: Dict[str, bool]) -> str:
        """
        Converts an action dictionary to a logical expression string (AND).
        If no actions are active, returns '[idle]'.
        """
        if not any(action_dict.values()):
            return "[idle]"

        parts = [var if val else f"~{var}" for var, val in action_dict.items()]
        return "(" + " & ".join(parts) + ")"

    def _generate_reduced_label(self, valid_formulas: List[str]) -> str:
        """
        Reduces a list of formulas to True if all action combinations are allowed,
        otherwise builds an OR expression for partial constraints.
        """
        all_permutations_count = 2 ** len(self.action_vars)
        if len(valid_formulas) >= all_permutations_count:
            return "true"
        return " | ".join(valid_formulas)

    def _build_partial_dot(self, active_transitions: List[Tuple[str, str]]) -> str:
        """
        Dynamically builds output DOT code for a set of extracted edges.
        """
        lines = [
            "digraph PartialDFA {",
            "  rankdir = LR;",
            f'  {self.current_state} [shape=doublecircle, style=filled, fillcolor=lightblue];'
        ]

        for dst, label in active_transitions:
            if dst != self.current_state:
                lines.append(f'  {dst} [shape=circle];')
            lines.append(f'  {self.current_state} -> {dst} [label="{label}"];')

        lines.append("}\n")
        return "\n".join(lines)

    def _label_to_bdd(self, label: str) -> Any:
        """
        Loads a label string into a BDD, handling tautology keywords in advance.
        """
        if label == "true":
            return self.bdd.true
        if label == "false":
            return self.bdd.false

        return self.bdd.add_expr(label)

    def _parse_dot_to_graph(self, dot_model: DotModel) -> None:
        """
        Populates self.transitions from the parsed DFA DOT model.
        """
        self.current_state = dot_model.init_target

        for edge in dot_model.edges:
            label = edge.attrs.get("label")
            if label is None:
                continue
            self.transitions.setdefault(edge.src, []).append((edge.dst, self._label_to_bdd(label)))
