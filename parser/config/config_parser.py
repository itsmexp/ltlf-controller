from pathlib import Path
from typing import List, Tuple

from lark import Lark, Transformer, UnexpectedInput

GRAMMAR_PATH = Path(__file__).with_name("config_grammar.lark")
CONFIG_GRAMMAR = GRAMMAR_PATH.read_text(encoding="utf-8")


class ConfigTransformer(Transformer):
    def name(self, items):
        return str(items[0])

    def list_line(self, items):
        return [str(item) for item in items]

    def rule_line(self, items):
        return str(items[0]).strip()

    def start(self, items):
        lists = [item for item in items if isinstance(item, list)]
        rules = [
            item.strip()
            for item in items
            if isinstance(item, str) and item.strip() and "." not in item
        ]
        if len(lists) < 2:
            raise ValueError("Config must start with [sensors] and [actions] lines.")
        sensors = lists[0]
        actions = lists[1]
        return sensors, actions, rules


CONFIG_PARSER = Lark(CONFIG_GRAMMAR, start="start", parser="lalr")


def load_formula_from_file(filepath: str) -> Tuple[str, List[str], List[str]]:
    with open(filepath, "r", encoding="utf-8") as file_obj:
        content = file_obj.read()

    try:
        parse_tree = CONFIG_PARSER.parse(content)
    except UnexpectedInput as exc:
        raise ValueError(
            f"Invalid config format at line {exc.line}, column {exc.column}."
        ) from exc

    sensors, actions, rules = ConfigTransformer().transform(parse_tree)

    if not rules:
        raise ValueError("No rules found. Add at least one LTLf rule ending with '.'.")

    formula = " & ".join(rules)

    print(f"[Config] Loaded {len(sensors)} sensors: {sensors}")
    print(f"[Config] Loaded {len(actions)} actions: {actions}")
    print(f"[Config] Loaded {len(rules)} rules, combined into formula.")

    return formula, sensors, actions
