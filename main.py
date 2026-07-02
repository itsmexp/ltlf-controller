import sys
import os
import argparse
import json
import random
import zipfile
import shutil
from pathlib import Path

from tempfile import TemporaryDirectory

from core.ltlf_controller import LTLfController

DEFAULT_STORAGE_DIR = Path.home() / ".ltlf_controller"
CONFIG_DIR = Path(sys.argv[0]).resolve().parent
CONFIG_FILE = CONFIG_DIR / "settings.json"

def get_storage_dir() -> Path:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                settings = json.load(f)
                custom_dir = settings.get("storage_dir")
                if custom_dir:
                    return Path(custom_dir)
        except Exception:
            pass
    return DEFAULT_STORAGE_DIR

STORAGE_DIR = get_storage_dir()

def _ensure_storage():
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)

def cmd_generate(args):
    if shutil.which("mona") is None:
        print("Error: The 'mona' executable was not found in your system PATH.", file=sys.stderr)
        print("MONA is a required system dependency for generating LTLf controllers.", file=sys.stderr)
        print("Please install it (e.g., 'sudo apt install mona' on Debian/Ubuntu).", file=sys.stderr)
        sys.exit(1)

    _ensure_storage()
    config_path = Path(args.config)
    name = args.name

    if not config_path.exists():
        print(f"Error: Config file '{config_path}' not found.", file=sys.stderr)
        sys.exit(1)

    print(f"Generating controller for '{name}'...", file=sys.stderr)
    try:
        controller = LTLfController(config_file=str(config_path), aggressive_pruning=True, prune=True)
    except Exception as e:
        print(f"Failed to generate controller: {e}", file=sys.stderr)
        sys.exit(1)

    out_file = STORAGE_DIR / f"{name}.ltlf"

    with TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        
        # 1. Export GraphML
        graphml_path = temp_dir_path / "graph.graphml"
        controller.export_graph(str(graphml_path))

        # 2. Save metadata
        metadata = {
            "name": name,
            "sensor_vars": controller.get_sensor_vars(),
            "action_vars": controller.get_action_vars()
        }
        metadata_path = temp_dir_path / "metadata.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        # 3. Copy original config
        config_copy_path = temp_dir_path / "config.txt"
        shutil.copy2(config_path, config_copy_path)

        # Zip it up
        with zipfile.ZipFile(out_file, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(graphml_path, "graph.graphml")
            zf.write(metadata_path, "metadata.json")
            zf.write(config_copy_path, "config.txt")

    print(f"Successfully generated and saved controller '{name}' at {out_file}", file=sys.stderr)


def cmd_list(args):
    _ensure_storage()
    files = list(STORAGE_DIR.glob("*.ltlf"))
    if not files:
        print("No controllers saved.")
        return

    print(f"{'NAME':<20} {'PATH'}")
    print("-" * 60)
    for f in files:
        name = f.stem
        print(f"{name:<20} {f.absolute()}")


def cmd_delete(args):
    _ensure_storage()
    name = args.name
    target = STORAGE_DIR / f"{name}.ltlf"
    if target.exists():
        target.unlink()
        print(f"Deleted controller '{name}'.")
    else:
        print(f"Controller '{name}' not found.")


def cmd_help(args):
    _ensure_storage()
    name = args.name
    target = STORAGE_DIR / f"{name}.ltlf"
    if not target.exists():
        print(f"Controller '{name}' not found.")
        return

    with zipfile.ZipFile(target, "r") as zf:
        metadata = json.loads(zf.read("metadata.json").decode("utf-8"))
        config_content = zf.read("config.txt").decode("utf-8")

    print(f"--- Controller: {name} ---")
    print(f"Sensor Variables: {', '.join(metadata['sensor_vars'])}")
    print(f"Action Variables: {', '.join(metadata['action_vars'])}")
    print("\n--- Original Configuration ---")
    print(config_content)


def cmd_info(args):
    print("--- LTLf Controller CLI ---")
    print("Version: 0.1.0")
    print("Description: Command-line tool for generating and serving LTLf-based controllers.")
    print(f"Storage Directory: {STORAGE_DIR.absolute()}")
    print("\nAvailable Commands:")
    print("  generate <config> --name <name>  : Generate and save a controller")
    print("  list                             : List all saved controllers")
    print("  serve                            : Start interactive server on stdin/stdout")
    print("  help <name>                      : Show variables and rules for a saved controller")
    print("  delete <name>                    : Delete a saved controller")
    print("  config [--storage-dir <path>]    : View or change CLI configuration")
    print("  info                             : Show this project information")


def cmd_config(args):
    if args.storage_dir:
        new_dir = Path(args.storage_dir).resolve()
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        settings = {}
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    settings = json.load(f)
            except Exception:
                pass
        
        settings["storage_dir"] = str(new_dir)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
        
        print(f"Storage directory updated to: {new_dir}")
        print("Note: Existing controllers in the old directory were NOT automatically moved.")
    else:
        print(f"Current Storage Directory: {STORAGE_DIR.absolute()}")
        if CONFIG_FILE.exists():
            print(f"Config File Location: {CONFIG_FILE.absolute()}")


def _load_controller(name: str) -> LTLfController:
    target = STORAGE_DIR / f"{name}.ltlf"
    if not target.exists():
        raise FileNotFoundError(f"Controller '{name}' not found in {STORAGE_DIR}")

    with TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        with zipfile.ZipFile(target, "r") as zf:
            zf.extractall(temp_dir_path)

        graphml_path = temp_dir_path / "graph.graphml"
        metadata_path = temp_dir_path / "metadata.json"

        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        return LTLfController(
            graphml_file=str(graphml_path),
            sensor_vars=metadata["sensor_vars"],
            action_vars=metadata["action_vars"],
            prune=False # already pruned during generation
        )


def cmd_serve(args):
    _ensure_storage()
    
    loaded_controllers = {}
    uuid_states = {}
    
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        
        if line.lower() == "exit":
            break

        parts = line.split(maxsplit=2)
        if len(parts) < 2:
            print(f"Error: Invalid input format. Expected 'name uuid [sensors...]', got '{line}'", file=sys.stderr)
            continue
            
        name = parts[0]
        uid = parts[1]
        sensors_str = parts[2] if len(parts) > 2 else ""

        # Parse sensors (handle comma or space separated)
        sensors_list = [s.strip() for s in sensors_str.replace(",", " ").split() if s.strip()]
        sensor_dict = {s: True for s in sensors_list}

        if name not in loaded_controllers:
            try:
                loaded_controllers[name] = _load_controller(name)
            except Exception as e:
                print(f"Error loading controller '{name}': {e}", file=sys.stderr)
                continue

        controller = loaded_controllers[name]

        if uid not in uuid_states:
            initial_state = controller._graph.graph.get("initial", "")
            uuid_states[uid] = initial_state

        curr_state = uuid_states[uid]

        # Get possible actions
        possible_actions = controller.get_possible_action_from_state(curr_state, sensor_dict)

        if not possible_actions:
            # Fallback if somehow stuck
            chosen_action = "idle"
            next_state = curr_state
        else:
            chosen_action = random.choice(possible_actions)
            next_state_cand = controller.get_next_state(curr_state, chosen_action, sensor_dict)
            if next_state_cand is not None:
                next_state = next_state_cand
            else:
                next_state = curr_state

        uuid_states[uid] = next_state

        # Print output
        # Output format: uuid action1 !action2 action3
        all_action_vars = controller.get_action_vars()
        active_actions = [] if chosen_action == "idle" else chosen_action.split("+")
        
        output_actions = []
        for a in all_action_vars:
            if a in active_actions:
                output_actions.append(a)
            else:
                output_actions.append(f"!{a}")
                
        print(f"{uid} {' '.join(output_actions)}")
        
        # Flush stdout so output is immediately available to caller
        sys.stdout.flush()


def main():
    parser = argparse.ArgumentParser(description="LTLf Controller CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    subparsers.required = True

    # Generate
    parser_gen = subparsers.add_parser("generate", help="Generate and save a controller from config")
    parser_gen.add_argument("config", help="Path to the config file")
    parser_gen.add_argument("--name", required=True, help="Name of the controller")
    parser_gen.set_defaults(func=cmd_generate)

    # List
    parser_list = subparsers.add_parser("list", help="List all saved controllers")
    parser_list.set_defaults(func=cmd_list)

    # Delete
    parser_del = subparsers.add_parser("delete", help="Delete a saved controller")
    parser_del.add_argument("name", help="Name of the controller to delete")
    parser_del.set_defaults(func=cmd_delete)

    # Help
    parser_help = subparsers.add_parser("help", help="Show info for a saved controller")
    parser_help.add_argument("name", help="Name of the controller")
    parser_help.set_defaults(func=cmd_help)

    # Serve
    parser_serve = subparsers.add_parser("serve", help="Start the interactive server on stdin/stdout")
    parser_serve.set_defaults(func=cmd_serve)

    # Info
    parser_info = subparsers.add_parser("info", help="Show project information")
    parser_info.set_defaults(func=cmd_info)

    # Config
    parser_config = subparsers.add_parser("config", help="Manage CLI configuration")
    parser_config.add_argument("--storage-dir", help="Set a new persistent storage directory")
    parser_config.set_defaults(func=cmd_config)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
