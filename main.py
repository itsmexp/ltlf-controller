"""Project entrypoint: build controller from a config file."""

import sys

from server.factory import build_controller_from_config


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <config_file.txt>")
        sys.exit(1)
    
    config_file = sys.argv[1]
    controller = None
    try:
        controller = build_controller_from_config(config_file)
        print("[Success] Controller initialized and ready.")
    except FileNotFoundError:
        print(f"Error: File '{config_file}' not found.")
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        if controller is not None:
            controller.close()
