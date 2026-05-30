from pathlib import Path
import re

from lark import Lark, Transformer

GRAMMAR_PATH = Path(__file__).with_name("declare_grammar.lark")
DECLARE_GRAMMAR = GRAMMAR_PATH.read_text(encoding="utf-8")


def _existence(n, x):
    if n == 1:
        return f"F({x})"
    return f"F({x} & X({_existence(n-1, x)}))"


class DeclareToLTLf(Transformer):
    def formula(self, items):
        name = items[0].value.lower()
        args = items[1]

        if name == "existence":
            if len(args) == 1:
                return f"F({args[0]})"
            elif len(args) == 2:
                return _existence(int(args[0]), args[1])

        elif name == "absence":
            if len(args) == 1:
                return f"!F({args[0]})"
            elif len(args) == 2:
                return f"!{_existence(int(args[0]), args[1])}"

        elif name == "exactly":
            if len(args) == 1:
                return f"({_existence(1, args[0])} & !{_existence(2, args[0])})"
            elif len(args) == 2:
                n = int(args[0])
                x = args[1]
                return f"({_existence(n, x)} & !{_existence(n+1, x)})"

        elif name == "init":
            return args[0]

        elif name == "choice":
            x, y = args
            return f"(F({x}) | F({y}))"

        elif name == "exclusive-choice":
            x, y = args
            return f"((F({x}) | F({y})) & !(F({x}) & F({y})))"

        elif name == "responded-existence":
            x, y = args
            return f"(F({x}) -> F({y}))"

        elif name == "coexistence":
            x, y = args
            return f"((F({x}) -> F({y})) & (F({y}) -> F({x})))"

        elif name == "response":
            x, y = args
            return f"G({x} -> F({y}))"

        elif name == "precedence":
            x, y = args
            return f"((!{y} U {x}) | G(!{y}))"

        elif name == "succession":
            x, y = args
            response = f"G({x} -> F({y}))"
            precedence = f"((!{y} U {x}) | G(!{y}))"
            return f"({response} & {precedence})"

        elif name == "alternate-response":
            x, y = args
            return f"G({x} -> X(!{x} U {y}))"

        elif name == "alternate-precedence":
            x, y = args
            precedence_xy = f"((!{y} U {x}) | G(!{y}))"
            return f"({precedence_xy} & G({y} -> X({precedence_xy})))"

        elif name == "alternate-succession":
            x, y = args
            alt_response = f"G({x} -> X(!{x} U {y}))"
            precedence_xy = f"((!{y} U {x}) | G(!{y}))"
            alt_precedence = f"({precedence_xy} & G({y} -> X({precedence_xy})))"
            return f"({alt_response} & {alt_precedence})"

        elif name == "chain-response":
            x, y = args
            return f"G({x} -> X({y}))"

        elif name == "chain-precedence":
            x, y = args
            return f"G(X({y}) -> {x})"

        elif name == "chain-succession":
            x, y = args
            return f"(G({x} -> X({y})) & G(X({y}) -> {x}))"

        elif name == "not-coexistence":
            x, y = args
            return f"!(F({x}) & F({y}))"

        elif name == "neg-succession":
            x, y = args
            return f"G({x} -> !F({y}))"

        elif name == "neg-chain-succession":
            x, y = args
            return f"G({x} -> !X({y}))"

        raise ValueError(f"Unknown DECLARE formula name: {name}")

    def args(self, items):
        return items

    def proposition(self, items):
        return items[0].value

    def number(self, items):
        return int(items[0].value)


declare_parser = Lark(DECLARE_GRAMMAR, parser="lalr", transformer=DeclareToLTLf())


TEMPLATE_RE = re.compile(r"^\s*([A-Za-z-]+)\s*\([^()]*\)\s*$")
DECLARE_TEMPLATES = {
    "existence",
    "absence",
    "exactly",
    "init",
    "choice",
    "exclusive-choice",
    "responded-existence",
    "coexistence",
    "response",
    "precedence",
    "succession",
    "alternate-response",
    "alternate-precedence",
    "alternate-succession",
    "chain-response",
    "chain-precedence",
    "chain-succession",
    "not-coexistence",
    "neg-succession",
    "neg-chain-succession",
}


def _split_top_level(text: str, sep: str):
    chunks = []
    depth = 0
    start = 0
    for idx, ch in enumerate(text):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                raise ValueError("Unbalanced parentheses in formula.")
        elif ch == sep and depth == 0:
            chunks.append(text[start:idx].strip())
            start = idx + 1
    if depth != 0:
        raise ValueError("Unbalanced parentheses in formula.")
    chunks.append(text[start:].strip())
    return [chunk for chunk in chunks if chunk]


def _wrap_formula(formula: str) -> str:
    formula = formula.strip()
    if formula.startswith("(") and formula.endswith(")"):
        return formula
    return f"({formula})"


def declare2ltlf(declare_input):
    if isinstance(declare_input, str):
        parts = _split_top_level(declare_input, "&")
    else:
        parts = [str(p).strip() for p in declare_input if str(p).strip()]

    out = []
    for p in parts:
        m = TEMPLATE_RE.match(p)
        if m and m.group(1).lower() in DECLARE_TEMPLATES:
            out.append(_wrap_formula(declare2ltlf_formula(p)))
        else:
            out.append(_wrap_formula(p))

    return " & ".join(out)


def declare2ltlf_formula(declare_formula: str):
    return declare_parser.parse(declare_formula.strip())
