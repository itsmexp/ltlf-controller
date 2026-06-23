import sys
import os
import subprocess

# Add PyInstaller temp dir to PATH so `mona` can be found
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    os.environ["PATH"] = sys._MEIPASS + os.pathsep + os.environ.get("PATH", "")
    # Patch ltlf2dfa relative path for .lark files
    import ltlf2dfa.parser
    ltlf2dfa.parser.CUR_DIR = os.path.join(sys._MEIPASS, "ltlf2dfa", "parser")

import ltlf2dfa.ltlf2dfa
def patched_invoke_mona():
    """Execute the MONA tool without UNIX-specific os.setsid/killpg."""
    command = "mona -q -u -w {}/automa.mona".format(ltlf2dfa.ltlf2dfa.PACKAGE_DIR)
    process = subprocess.Popen(
        args=command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True,
        encoding="utf-8",
    )
    try:
        output, error = process.communicate(timeout=30)
        return str(output).strip()
    except subprocess.TimeoutExpired:
        process.kill()
        return False
ltlf2dfa.ltlf2dfa.invoke_mona = patched_invoke_mona

# Import the actual main module and run it
import main

if __name__ == "__main__":
    main.main()
