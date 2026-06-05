from pathlib import Path
import re

from lark import Lark, Transformer

GRAMMAR_PATH = Path(__file__).with_name("almanac_grammar.lark")
ALMANAC_GRAMMAR = GRAMMAR_PATH.read_text(encoding="utf-8")

class AlmanacToLTLf(Transformer):
    def formula(self, items):
        raw_name = items[0].value
        name = raw_name.strip().lower()
        args = items[1]

        # se leggo in dovrò rispondere out entro gli n prossimi step
        if name == "reactive_response":
            if len(args) not in (2, 3):
                raise ValueError("reactive_response expects 2 or 3 arguments")
            in_atom, out_atom = args[0], args[1]
            n = args[2] if len(args) == 3 else 0
            if not isinstance(n, int) or n < 0:
                raise ValueError("reactive_response: n must be a non-negative integer")
            
            formula_str = out_atom
            for _ in range(n):
                formula_str = f"({out_atom} | X({formula_str}))"
            return f"G({in_atom} -> {formula_str})"

        # se leggo in non potrò mai rispondere out
        if name == "inhibition":
            if len(args) != 2:
                raise ValueError("inhibition expects 2 arguments")
            in_atom, out_atom = args
            return f"G({in_atom} -> G(!{out_atom}))"

        # se leggo in non potrò rispondere out per i prossimi n step
        if name == "reactive_inhibition":
            if len(args) not in (2, 3):
                raise ValueError("reactive_inhibition expects 2 or 3 arguments")
            in_atom, out_atom = args[0], args[1]
            n = args[2] if len(args) == 3 else 0
            if not isinstance(n, int) or n < 0:
                raise ValueError("reactive_inhibition: n must be a non-negative integer")

            formula_str = f"!{out_atom}"
            for _ in range(n):
                # Utilizziamo WX (Weak Next) al posto del costrutto (last | X(...))
                formula_str = f"(!{out_atom} & WX({formula_str}))"
            return f"G({in_atom} -> {formula_str})"

        # se leggo in_start dovrò rispondere out fin quando non leggerò in_end
        if name == "reactive_persistence_response":
            if len(args) not in (2, 3):
                raise ValueError("reactive_persistence_response expects 2 or 3 arguments")
            
            if len(args) == 3:
                in_start, in_end, out_action = args
                return f"G(({in_start} & !{in_end}) -> (({out_action} U {in_end}) | G({out_action})))"
            else:
                in_start, out_action = args
                return f"G({in_start} -> (({out_action} U !{in_start}) | G({out_action})))"

        # se leggo in_start non potrò rispondere out fin quando non leggerò in_end (oppure finirà la traccia)
        if name == "reactive_persistence_inhibition":
            if len(args) != 3:
                raise ValueError("reactive_persistence_inhibition expects 3 arguments")
            in_start, in_end, out_action = args
            return f"G(({in_start} & !{in_end}) -> (!{out_action} U ({in_end} | last)))"

        # vi è una precedenza tra le risposte
        if name == "proactive_chain":
            if len(args) < 2:
                raise ValueError("proactive_chain expects at least 2 arguments")
            parts = []
            for i in range(1, len(args)):
                prereq = args[i - 1]
                target = args[i]
                parts.append(f"((!{target} U {prereq}) | G(!{target}))")
            return f"({ ' & '.join(parts) })"

        # se rispondo un out_i non potrò più rispondere out_j con j != i sull'intera traccia
        if name == "proactive_exclusion":
            if len(args) < 2:
                raise ValueError("proactive_exclusion expects at least 2 arguments")
            pairs = []
            for i in range(len(args)):
                for j in range(i + 1, len(args)):
                    pairs.append(f"!(F({args[i]}) & F({args[j]}))")
            inner = " & ".join(pairs)
            return f"({inner})"

        # in uno step posso rispondere al massimo a una delle risposte
        if name == "proactive_step_exclusion":
            if len(args) < 2:
                raise ValueError("proactive_step_exclusion expects at least 2 arguments")
            pairs = []
            for i in range(len(args)):
                for j in range(i + 1, len(args)):
                    pairs.append(f"!({args[i]} & {args[j]})")
            inner = " & ".join(pairs)
            return f"G({inner})"

        # alternanza stretta tra out_a e out_b
        if name == "proactive_alternate":
            if len(args) != 2:
                raise ValueError("proactive_alternate expects 2 arguments")
            out_a, out_b = args
            part_a = f"G({out_a} -> X(!{out_a} U ({out_b} | last)))"
            part_b = f"G({out_b} -> X(!{out_b} U ({out_a} | last)))"
            return f"({part_a} & {part_b})"

        # setup stato iniziale
        if name == "initial_state":
            if len(args) != 1:
                raise ValueError("initial_state expects 1 argument")
            atom, = args
            return f"{atom}"

        raise ValueError(f"Unknown template name: {name}")

    def args(self, items):
        return items

    def proposition(self, items):
        return items[0].value

    def number(self, items):
        return int(items[0].value)


almanac_parser = Lark(ALMANAC_GRAMMAR, parser="lalr", transformer=AlmanacToLTLf())

TEMPLATE_RE = re.compile(r"^\s*([A-Za-z0-9_\-]+)\s*\([^()]*\)\s*;?\s*$")
ALMANAC_TEMPLATES = {
    "reactive_response",
    "inhibition",
    "reactive_inhibition",
    "reactive_persistence_response",
    "reactive_persistence_inhibition",
    "proactive_chain",
    "proactive_exclusion",
    "proactive_step_exclusion",
    "proactive_alternate",
    "initial_state",
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

def almanac2ltlf(almanac_input):
    if isinstance(almanac_input, str):
        parts = _split_top_level(almanac_input, "&")
    else:
        parts = [str(p).strip() for p in almanac_input if str(p).strip()]

    out = []
    for p in parts:
        m = TEMPLATE_RE.match(p)
        if m:
            template_name = m.group(1).strip().lower()
            if template_name in ALMANAC_TEMPLATES:
                out.append(_wrap_formula(almanac2ltlf_formula(p)))
                continue
        out.append(_wrap_formula(p))

    return " & ".join(out)

def almanac2ltlf_formula(almanac_formula: str) -> str:
    s = almanac_formula.strip()
    if s.endswith(";"):
        s = s[:-1].rstrip()
    try:
        return str(almanac_parser.parse(s))
    except Exception as e:
        raise ValueError(f"Failed to parse almanac template '{almanac_formula}': {e}") from e