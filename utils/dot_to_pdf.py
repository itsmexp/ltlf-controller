from __future__ import annotations

from pathlib import Path

import graphviz


def convert_dot_to_pdf(dot_source: str, pdf_path: str | None = None) -> str:
    output_path = Path(pdf_path) if pdf_path else Path("graph.pdf")
    pdf_file = output_path if output_path.suffix.lower() == ".pdf" else output_path.with_suffix(".pdf")
    pdf_file.write_bytes(graphviz.Source(dot_source).pipe(format="pdf"))
    return str(pdf_file)
