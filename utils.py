"""Graph helper utilities (rendering helpers)."""

import subprocess
import tempfile


def render_dot_to_png(dot_content: str, output_path: str) -> bool:
    """Render DOT string to PNG via Graphviz `dot`. Returns success flag."""
    return _render_dot(dot_content, output_path, "png")

def render_dot_to_pdf(dot_content: str, output_path: str) -> bool:
    """Render DOT string to high-quality PDF via Graphviz `dot`. Returns success flag."""
    return _render_dot(dot_content, output_path, "pdf")

def _render_dot(dot_content: str, output_path: str, fmt: str) -> bool:
    """Internal helper to render DOT string to specified format."""
    if not dot_content:
        print(f"[Utility] No DOT content provided for {output_path}.")
        return False

    # Ensure output file has the correct extension
    if not output_path.endswith(f'.{fmt}'):
        output_path += f".{fmt}"

    try:
        # Use a safe temporary file that is automatically cleaned up or safely removed
        with tempfile.NamedTemporaryFile(mode='w', suffix='.dot', delete=False) as temp_dot_file:
            temp_dot_file.write(dot_content)
            temp_dot_path = temp_dot_file.name

        # Run graphviz dot
        result = subprocess.run(
            ["dot", f"-T{fmt}", temp_dot_path, "-o", output_path],
            check=True,
            capture_output=True,
            text=True
        )
        print(f"[Utility] {fmt.upper()} generated and saved to {output_path}")
        return True
    except FileNotFoundError:
        print("[Utility] Graphviz 'dot' not found. Please install it.")
        return False
    except subprocess.CalledProcessError as e:
        print(f"[Utility] Graphviz failed with error code {e.returncode}: {e.stderr}")
        return False
    except Exception as e:
        print(f"[Utility] Unexpected error: {e}")
        return False
    finally:
        # Cleanup temporary dot file
        try:
            import os
            if 'temp_dot_path' in locals() and os.path.exists(temp_dot_path):
                os.remove(temp_dot_path)
        except Exception:
            pass
