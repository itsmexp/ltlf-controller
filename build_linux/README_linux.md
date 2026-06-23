# Linux Build Guide

On Linux, `ltlf_controller` operates as a Python CLI application and utilizes the system's natively installed `mona` package.

## Prerequisites
- Python 3.8+
- `pip`
- `mona` (System package)

## Installation Steps

1. **Install MONA natively**
   For Debian/Ubuntu based systems:
   ```bash
   sudo apt update && sudo apt install mona
   ```

2. **Install the CLI package**
   Navigate to the root directory of the project and install it in your environment:
   ```bash
   pip install -e .
   ```
   Or using `pipx` for global isolation:
   ```bash
   pipx install .
   ```

3. **Verify Installation**
   Run the CLI directly from your terminal:
   ```bash
   ltlf_controller info
   ```

Unlike Windows, you do not need to use PyInstaller to bundle dependencies, as the UNIX environment natively supports the `os.setsid()` signals required by `ltlf2dfa`, and MONA runs natively without Cygwin.
