"""
ltlf_controller.py
------------------
Class responsible for compiling and managing behavioral patterns
through DFA conversion of LTLf expressions and partial extraction with BDDs.
"""

from typing import Dict, List, Optional

from utils.ltlf_automaton import build_ltlf_controller_runtime


class LTLfController:
    """
    Generates a DFA automaton from an LTLf specification over a set
    of variables. Integrates BDDs (Binary Decision Diagrams) for efficient
    logical pattern matching over possible decisions at each state.
    """

    def __init__(
        self,
        formula_str: str,
        sensor_vars: List[str],
        action_vars: List[str]
    ):
        """
        Initializes the LTLf controller from a formula.

        :param formula_str: LTLf logic formula as a string.
        :param sensor_vars: List of variables defining world state (sensors).
        :param action_vars: List of variables defining possible actions.
        """
        self.formula_str: str = formula_str
        self.sensor_vars: List[str] = sensor_vars
        self.action_vars: List[str] = action_vars
        self._runtime = build_ltlf_controller_runtime(
            formula_str, sensor_vars, action_vars
        )

    @property
    def initial_state(self) -> Optional[str]:
        return self._runtime.initial_state

    @property
    def current_state(self) -> Optional[str]:
        return self._runtime.current_state

    @property
    def all_states(self):
        return self._runtime.all_states

    def visible_transitions(self, sensor_dict: Dict[str, bool]):
        return self._runtime.visible_transitions(sensor_dict)

    def get_possible_action(self, sensor_dict: Dict[str, bool]) -> List[str]:
        """
        Returns feasible move combinations from the current state,
        filtered by current sensor constraints.

        :param sensor_dict: Sensor map with current values (e.g. {"s1": True}).
        :return: List of strings (e.g. ["idle", "a1"]).
        """
        return self._runtime.get_possible_action(sensor_dict)

    def choose_action(self, move_str: str) -> bool:
        """
        Applies the chosen move to the automaton and updates internal state.

        :param move_str: Move identifier string, joined by '+' (e.g. "a1+a2" or "idle").
        :return: True if move is allowed and the node advances, False otherwise.
        """
        return self._runtime.choose_action(move_str)

    def close(self):
        """
        Force-clears internal BDD objects by deleting the transition map.
        Prevents leaking dangling nodes in memory after execution.
        """
        self._runtime.close()
