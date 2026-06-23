# Windows Build Guide

To build a standalone `.exe` that includes Python and `MONA`, follow these steps on a Windows machine.
Because MONA is inherently a UNIX tool, we include its Windows executable (`mona.exe`) along with its Cygwin dependency (`cygwin1.dll`) locally in this folder, and PyInstaller bundles them automatically.

## Prerequisites
- Python 3.8+ installed on Windows
- `pip` installed

## Compilation Steps

1. Install PyInstaller:
   ```bash
   pip install pyinstaller
   ```

2. Open your terminal and navigate to the `build_windows` directory:
   ```bash
   cd build_windows
   ```

3. Ensure that `mona.exe` and `cygwin1.dll` are present in this folder.

4. Run PyInstaller using the provided `.spec` file:
   ```bash
   python -m PyInstaller ltlf_controller.spec --clean -y
   ```

5. The generated standalone executable will be available in the `dist/` folder under `build_windows/dist/ltlf_controller.exe`.

## How it works
The `entry_point.py` script applies patches to the `ltlf2dfa` dependency at runtime to make it compatible with Windows systems (circumventing the lack of POSIX `os.setsid()` and similar). When the user runs the executable, it extracts `mona.exe` to a temporary directory (`sys._MEIPASS`), appends it to the `PATH`, and launches the application.
