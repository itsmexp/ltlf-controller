from typing import Dict

from ltlf_controller import LTLfController

controllers: Dict[str, LTLfController] = {}


def log(message: str) -> None:
    print(f"[API] {message}")
