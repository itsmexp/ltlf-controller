from __future__ import annotations

from pathlib import Path

import graphviz
import re


def convert_dot_to_pdf(dot_source: str, pdf_path: str | None = None) -> str:
    output_path = Path(pdf_path) if pdf_path else Path("graph.pdf")
    pdf_file = output_path if output_path.suffix.lower() == ".pdf" else output_path.with_suffix(".pdf")
    pdf_file.write_bytes(graphviz.Source(dot_source).pipe(format="pdf"))
    return str(pdf_file)

def convert_dot_to_png(dot_source: str, png_path: str | None = None) -> str:
    output_path = Path(png_path) if png_path else Path("graph.png")
    png_file = output_path if output_path.suffix.lower() == ".png" else output_path.with_suffix(".png")
    png_file.write_bytes(graphviz.Source(dot_source).pipe(format="png"))
    return str(png_file)