"""Run the LTLf Controller API server with Flask."""

from flask import Flask, jsonify, request
from typing import Optional

from core.ltlf_controller import LTLfController
from parser.config.config_parser import load_formula_from_file

# --- App Setup ---
app = Flask(__name__)

# Global state for the single LTLf controller
GLOBAL_CONTROLLER: Optional[LTLfController] = None


@app.route("/health", methods=["GET"])
def health():
    print("GET /health")
    return jsonify({"status": "ok"})


@app.route("/api/initialize", methods=["POST"])
def initialize():
    global GLOBAL_CONTROLLER
    try:
        data = request.get_json() or {}
        config_file = data.get("config_file")

        print(f"POST /api/initialize | config_file={config_file!r}")

        if not config_file:
            print("Missing 'config_file' parameter")
            return jsonify({"error": "Missing 'config_file' parameter"}), 400

        if GLOBAL_CONTROLLER is not None:
            print("Closing existing controller")
            GLOBAL_CONTROLLER.close()

        formula, sensors, actions = load_formula_from_file(config_file)
        GLOBAL_CONTROLLER = LTLfController(formula, sensors, actions)
        
        print("Controller initialized")
        return jsonify({"status": "success", "message": "Controller initialized"}), 200
    except FileNotFoundError as e:
        print(f"Error: file not found: {e}")
        return jsonify({"error": str(e)}), 404
    except ValueError as e:
        print(f"Error: invalid config: {e}")
        return jsonify({"error": str(e)}), 400


@app.route("/api/get_possible_action", methods=["POST"])
def get_possible_action():
    data = request.get_json() or {}
    sensors = data.get("sensors", {})

    print(f"POST /api/get_possible_action | sensors={sensors}")

    if GLOBAL_CONTROLLER is None:
        print("Error: controller not initialized")
        return jsonify({"error": "Controller is not initialized"}), 404

    try:
        valid_actions = GLOBAL_CONTROLLER.get_possible_action(sensors)
        print(f"valid_actions={valid_actions}")
        return jsonify({"valid_actions": valid_actions}), 200
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/choose_action", methods=["POST"])
def choose_action():
    data = request.get_json() or {}
    action = data.get("action")

    print(f"POST /api/choose_action | action={action!r}")

    if GLOBAL_CONTROLLER is None:
        print("Error: controller not initialized")
        return jsonify({"error": "Controller is not initialized"}), 404

    if not action:
        print("Missing 'action' parameter")
        return jsonify({"error": "Missing 'action' parameter"}), 400

    success = GLOBAL_CONTROLLER.choose_action(action)

    if success:
        print("Success")
        return jsonify({
            "status": "success",
            "message": f"Transitioned successfully using action '{action}'."
        }), 200

    print(f"Forbidden action={action!r}")
    return jsonify({
        "error": f"Action '{action}' is not allowed in the current state."
    }), 403


@app.route("/api/close", methods=["POST"])
def close():
    global GLOBAL_CONTROLLER
    print("POST /api/close")

    if GLOBAL_CONTROLLER is None:
        print("Error: controller not initialized")
        return jsonify({"error": "Controller is not initialized"}), 404

    GLOBAL_CONTROLLER.close()
    GLOBAL_CONTROLLER = None

    print("Released controller")
    return jsonify({
        "status": "success",
        "message": "Controller closed and released successfully."
    }), 200


if __name__ == "__main__":
    print("Starting Flask API server")
    print("Host: 0.0.0.0")
    print("Port: 8000")
    print("Available endpoints: /health, /api/initialize, /api/get_possible_action, /api/choose_action, /api/close")
    
    app.run(host="0.0.0.0", port=8000, debug=False)
