from pathlib import Path
import re

from lark import Lark, Transformer

GRAMMAR_PATH = Path(__file__).with_name("almanac_grammar.lark")
ALMANAC_GRAMMAR = GRAMMAR_PATH.read_text(encoding="utf-8")


def _negate(atom: str) -> str:
    """Negate an atom, simplifying double negation: !!x -> x, !(!x) -> x."""
    atom = atom.strip()
    # Handle (!expr) -> expr (double negation through parens)
    if atom.startswith("(!") and atom.endswith(")"):
        inner = atom[2:-1]
        return f"({inner})"
    if atom.startswith("!"):
        return atom[1:]
    return f"!{atom}"


class AlmanacToLTLf(Transformer):
    def formula(self, items):
        raw_name = items[0].value
        name = raw_name.strip().lower()
        args = items[1]


        # response(a, b, [n])
        # if n is not provided, it means that b must be in the same step.
        # if n > 0, it means that b should happen within n steps if a happens.
        if name == "response":
            if len(args) not in (2, 3):
                raise ValueError("response expects 2 or 3 arguments")
            in_atom, out_atom = args[0], args[1]
            n = 0
            if len(args) == 3:
                n = args[2]
            if not isinstance(n, int) or n < 0:
                raise ValueError("response: n must be a non-negative integer")

            if n == 0:
                return f"G({in_atom} -> {out_atom})"
            formula_str = out_atom
            for _ in range(n):
                formula_str = f"({out_atom} | X({formula_str}))"
            return f"G({in_atom} -> {formula_str})"

        # inhibition(a, b, [n])
        # if n is not provided, it means that b should not appen in the same step as a.
        # if n > 0, it means that b should never happen within n steps if a happens.
        if name == "inhibition":
            if len(args) not in (2, 3):
                raise ValueError("inhibition expects 2 or 3 arguments")
            in_atom, out_atom = args[0], args[1]
            n = 0
            if len(args) == 3:
                n = args[2]
            if not isinstance(n, int) or n < 0:
                raise ValueError("inhibition: n must be a non-negative integer")
            neg_out = _negate(out_atom)
            formula_str = neg_out
            for _ in range(n):
                formula_str = f"({neg_out} & WX({formula_str}))"
            return f"G({in_atom} -> {formula_str})"

        # persistence_response(a, b, c)
        # if a and not b, then c must happen until b happens
        if name == "persistence_response":
            if len(args) != 3:
                raise ValueError("persistence_response expects 3 arguments")
            in_start, in_end, out_action = args
            return f"G(({in_start} & {_negate(in_end)}) -> (({out_action} U {in_end}) | G({out_action})))"

        # persistence_inhibition(a, b, c)
        # if a and not b, then c must not happen until b happens
        if name == "persistence_inhibition":
            if len(args) != 3:
                raise ValueError("persistence_inhibition expects 3 arguments")
            in_start, in_end, out_action = args
            return f"G(({in_start} & {_negate(in_end)}) -> (({_negate(out_action)} U {in_end}) | G({_negate(out_action)})))"


        # chain(a, b, c, ...)
        # b cannot happen unless a happens first, c cannot happen unless b happens first, ...
        if name == "chain":
            if len(args) < 2:
                raise ValueError("chain expects at least 2 arguments")
            parts = []
            for i in range(1, len(args)):
                prereq = args[i - 1]
                target = args[i]
                neg_target = _negate(target)
                parts.append(f"(({neg_target} U {prereq}) | G({neg_target}))")
            return f"({ ' & '.join(parts) })"

        # exclusion(a, b, c, ...)
        # if a happens, b cannot happen and if b happens, a cannot happen. (general exclusion)
        if name == "exclusion":
            if len(args) < 2:
                raise ValueError("exclusion expects at least 2 arguments")
            pairs = []
            for i in range(len(args)):
                for j in range(len(args)):
                    if i != j:
                        pairs.append(f"!({args[i]} & F({args[j]}))")
            inner = " & ".join(pairs)
            return f"G({inner})"

        # step_exclusion(a, b, c, ...)
        # if a happens, b cannot happen and if b happens, a cannot happen at the same step. (step exclusion)
        if name == "step_exclusion":
            if len(args) < 2:
                raise ValueError("step_exclusion expects at least 2 arguments")
            pairs = []
            for i in range(len(args)):
                for j in range(i + 1, len(args)):
                    pairs.append(f"!({args[i]} & {args[j]})")
            inner = " & ".join(pairs)
            return f"G({inner})"

        # alternate(a, b)
        # a and b must alternate, and they cannot happen at the same step. They can both be false at the same step.
        # cannot have two a in the sequence with no b in between. (adiacent or not)
        # same for b
        if name == "alternate":
            if len(args) != 2:
                raise ValueError("alternate expects 2 arguments")
            out_a, out_b = args
            return f"G(!(({out_a} & {out_b})) & (({out_a} -> WX(({_negate(out_a)} U {out_b}) | G({_negate(out_a)}))) & ({out_b} -> WX(({_negate(out_b)} U {out_a}) | G({_negate(out_b)})))))"

        # cooldown(a, [n])
        # if a happens, it cannot happen again for n steps.
        # n is optional, if not provided, it is 1.
        if name == "cooldown":
            if len(args) not in [1, 2]:
                raise ValueError("cooldown expects 1 or 2 arguments")
            n = 1 if len(args) == 1 else args[1]
            if not isinstance(n, int) or n < 1:
                raise ValueError("cooldown expects second argument to be integer >= 1")
            out_atom = args[0]
            neg_out = _negate(out_atom)
            nexts = []
            for i in range(1, n + 1):
                nexts.append(f"{('WX(' * i)}({neg_out}){')' * i}")
            inner = " & ".join(nexts)
            return f"G({out_atom} -> ({inner}))"

        
        # initial_state(a)
        # a must hold at the initial state.
        if name == "initial_state":
            if len(args) != 1:
                raise ValueError("initial_state expects 1 argument")
            atom = args[0]
            return f"{atom}"

        #last_state(a)
        # a must hold at the final state.
        if name == "last_state":
            if len(args) != 1:
                raise ValueError("last_state expects 1 argument")
            atom = args[0]
            return f"G(last ->{atom})"

        raise ValueError(f"Unknown template name: {name}")

    def args(self, items):
        wrapped = []
        for item in items:
            if isinstance(item, str):
                if item.startswith("(") and item.endswith(")"):
                    wrapped.append(item)
                else:
                    wrapped.append(f"({item})")
            else:
                wrapped.append(item)
        return wrapped

    def proposition(self, items):
        return items[0].value

    def bool_neg(self, items):
        return _negate(items[0])

    def bool_and(self, items):
        return "(" + " & ".join(items) + ")"

    def bool_or(self, items):
        return "(" + " | ".join(items) + ")"

    def number(self, items):
        return int(items[0].value)


almanac_parser = Lark(ALMANAC_GRAMMAR, parser="lalr", transformer=AlmanacToLTLf())


TEMPLATE_RE = re.compile(r"^\s*([A-Za-z0-9_\-]+)\s*\(.*\)\s*;?\s*$")
ALMANAC_TEMPLATES = {
    "response",
    "inhibition",
    "persistence_response",
    "persistence_inhibition",
    "chain",
    "exclusion",
    "step_exclusion",
    "alternate",
    "cooldown",
    "initial_state",
    "last_state"
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

    non_empty_chunks = []
    for chunk in chunks:
        if chunk:
            non_empty_chunks.append(chunk)

    return non_empty_chunks


def _wrap_formula(formula: str) -> str:
    formula = formula.strip()
    if formula.startswith("(") and formula.endswith(")"):
        return formula
    return f"({formula})"


def almanac2ltlf(almanac_input):
    if isinstance(almanac_input, str):
        parts = _split_top_level(almanac_input, "&")
    else:
        parts = []
        for part in almanac_input:
            stripped_part = str(part).strip()
            if stripped_part:
                parts.append(stripped_part)

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

if __name__ == "__main__":
    import sys
    from pathlib import Path
    
    # Add project root to sys.path to allow absolute imports
    project_root = Path(__file__).resolve().parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    import tempfile
    import os
    from core.ltlf_controller import LTLfController
    from utils.dot_to_pdf import convert_dot_to_png

    dict_test = {
        "response": ("response(a, b)", "response.png"),
        "response_2": ("response(a, b, 2)", "response_2.png"),
        "inhibition": ("inhibition(a, b, 2)", "inhibition.png"),
        "persistence_response": ("persistence_response(a, b, c)", "persistence_response.png"),
        "persistence_inhibition": ("persistence_inhibition(a, b, c)", "persistence_inhibition.png"),
        "chain": ("chain(a, b, c)", "chain.png"),
        "exclusion": ("exclusion(a, b, c)", "exclusion.png"),
        "step_exclusion": ("step_exclusion(a, b, c)", "step_exclusion.png"),
        "alternate": ("alternate(a, b)", "alternate.png"),
        "cooldown": ("cooldown(a, 3)", "cooldown.png"),
        "initial_state": ("initial_state(a)", "initial_state.png"),
        "last_state": ("last_state(a)", "last_state.png"),
    }

    output_dir = project_root / "graphs"
    output_dir.mkdir(exist_ok=True)

    formulas_log = []

    for template_name, (formula_str, png_name) in dict_test.items():
        print(f"Generating {template_name} graph...")
        ltlf_formula = almanac2ltlf(formula_str)
        formulas_log.append(f"=== {template_name} ===\nAlmanac: {formula_str}\nLTLf: {ltlf_formula}\n")

        # Create a temporary config file with dummy sensors and actions to satisfy config parser requirements
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("#action: a, b, c.\n")
            f.write("#sensor: s.\n")
            f.write(f"#rule: {formula_str}.\n")
            temp_path = f.name

        try:
            controller = LTLfController(config_file=temp_path, aggressive_pruning=False, prune=False)
            dfa_dot = controller.get_graph_dot(acceptance_view=True)
            convert_dot_to_png(dfa_dot, str(output_dir / png_name))
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
    # Save formulas map to formulas.txt
    with open(output_dir / "formulas.txt", "w", encoding="utf-8") as f_out:
        f_out.write("\n".join(formulas_log))
    
    