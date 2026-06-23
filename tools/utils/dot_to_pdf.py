from __future__ import annotations

from pathlib import Path
from ltlf2dfa.parser.ltlf import LTLfParser

import graphviz
import re


def convert_dot_to_pdf(dot_source: str, pdf_path: str | None = None) -> str:
    if pdf_path:
        output_path = Path(pdf_path)
    else:
        output_path = Path("graph.pdf")

    if output_path.suffix.lower() == ".pdf":
        pdf_file = output_path
    else:
        pdf_file = output_path.with_suffix(".pdf")

    pdf_file.write_bytes(graphviz.Source(dot_source).pipe(format="pdf"))
    return str(pdf_file)


def convert_dot_to_png(dot_source: str, png_path: str | None = None) -> str:
    if png_path:
        output_path = Path(png_path)
    else:
        output_path = Path("graph.png")

    if output_path.suffix.lower() == ".png":
        png_file = output_path
    else:
        png_file = output_path.with_suffix(".png")

    png_file.write_bytes(graphviz.Source(dot_source).pipe(format="png"))
    return str(png_file)

if __name__ == "__main__":
    with open("out.dot", "r") as f:
        dot_source = f.read()

    print(convert_dot_to_png(dot_source, "out.png"))

