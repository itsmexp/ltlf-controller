import re
from typing import List, Tuple

import logging

from parser.almanac.almanac_parser import almanac2ltlf

DIRECTIVE_RE = re.compile(r"^\s*#\s*(action|sensor|rule)\s*:\s*(.*)$", re.IGNORECASE)


def _split_names(text: str) -> List[str]:
    cleaned = text.strip().rstrip(".")
    return [item.strip() for item in cleaned.split(",") if item.strip()]


def _split_rules(text: str) -> List[str]:
    cleaned = text.strip().rstrip(".")
    return [item.strip() for item in cleaned.split(";") if item.strip()]


def _load_directive_config(content: str) -> Tuple[str, List[str], List[str]]:
    sections = {"action": [], "sensor": [], "rule": []}
    current_section = None
    buffer: List[str] = []

    def flush() -> None:
        nonlocal buffer
        if current_section is None or not buffer:
            buffer = []
            return
        sections[current_section].append(" ".join(buffer).strip())
        buffer = []

    for raw_line in content.splitlines():
        stripped_line = raw_line.strip()
        if not stripped_line or stripped_line.startswith("%"):
            continue

        directive_match = DIRECTIVE_RE.match(stripped_line)
        if directive_match:
            flush()
            current_section = directive_match.group(1).lower()
            remainder = directive_match.group(2).strip()
            if remainder:
                buffer.append(remainder)
            continue

        if current_section is None:
            raise ValueError("Invalid config format. Add #action, #sensor and #rule directives.")

        buffer.append(stripped_line)

    flush()

    actions = _split_names(" ".join(sections["action"]))
    sensors = _split_names(" ".join(sections["sensor"]))
    rules = _split_rules(" ".join(sections["rule"]))

    # normalize and deduplicate while preserving order
    def _uniq_keep_order(items):
        seen = set()
        out = []
        for it in items:
            if it not in seen:
                seen.add(it)
                out.append(it)
        return out

    actions = _uniq_keep_order([a.strip() for a in actions])
    sensors = _uniq_keep_order([s.strip() for s in sensors])

    # 'last' is an internal LTLf atom and must not be a user action/sensor.
    actions = [a for a in actions if a.lower() != "last"]
    sensors = [s for s in sensors if s.lower() != "last"]

    if not actions:
        raise ValueError("No actions found. Add at least one name in the #action directive.")
    if not sensors:
        raise ValueError("No sensors found. Add at least one name in the #sensor directive.")
    if not rules:
        raise ValueError("No rules found. Add at least one formula in the #rule directive.")

    try:
        formula = almanac2ltlf(rules)
    except Exception as e:
        raise ValueError(f"Failed to parse rules in config: {e}") from e

    return formula, sensors, actions


def _has_directive_config(content: str) -> bool:
    for raw_line in content.splitlines():
        stripped_line = raw_line.strip()
        if not stripped_line or stripped_line.startswith("%"):
            continue
        if DIRECTIVE_RE.match(stripped_line):
            return True
    return False


def load_formula_from_file(filepath: str) -> Tuple[str, List[str], List[str]]:
    with open(filepath, "r", encoding="utf-8") as file_obj:
        content = file_obj.read()
    if not _has_directive_config(content):
        raise ValueError(
            "Invalid config format. Use only #action, #sensor and #rule directives."
        )

    formula, sensors, actions = _load_directive_config(content)

    logger = logging.getLogger(__name__)
    logger.info(f"Loaded {len(sensors)} sensors: {sensors}")
    logger.info(f"Loaded {len(actions)} actions: {actions}")
    logger.info("Loaded directive-based rules, combined into formula.")

    return formula, sensors, actions
