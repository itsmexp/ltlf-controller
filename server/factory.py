from ltlf_controller import LTLfController

from parser.config.config_parser import load_formula_from_file


def build_controller_from_config(config_file: str) -> LTLfController:
    formula, sensors, actions = load_formula_from_file(config_file)
    return LTLfController(formula, sensors, actions)
