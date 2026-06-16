import os
import uuid
import threading
import random
from flask import Flask, request, jsonify
from core.ltlf_controller import LTLfController

app = Flask(__name__)

# Global storage for controllers (in-memory sessions)
controllers = {}
controllers_lock = threading.Lock()

# Temporary directory inside the workspace for temporary config/export files
WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMP_DIR = os.path.join(WORKSPACE_DIR, "temp")
os.makedirs(TEMP_DIR, exist_ok=True)

@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS,DELETE"
    return response

@app.route("/initialize", methods=["POST"])
def initialize():
    data = request.json or {}
    config_content = data.get("config")
    export_content = data.get("export")
    sensor_vars = data.get("sensor_vars")
    action_vars = data.get("action_vars")
    aggressive_pruning = data.get("aggressive_pruning", False)
    prune = data.get("prune", True)

    if not config_content and not export_content:
        return jsonify({"error": "Missing 'config' or 'export' string content in request body"}), 400

    controller_uuid = str(uuid.uuid4())
    temp_file_path = None

    try:
        if config_content:
            # Initialize from configuration file content
            temp_file_path = os.path.join(TEMP_DIR, f"config_{controller_uuid}.txt")
            with open(temp_file_path, "w", encoding="utf-8") as f:
                f.write(config_content)
            
            controller = LTLfController(
                config_file=temp_file_path,
                aggressive_pruning=aggressive_pruning,
                prune=prune
            )
        else:
            # Initialize from export content (GraphML)
            if not sensor_vars or not action_vars:
                return jsonify({"error": "'sensor_vars' and 'action_vars' list are required when initializing from export"}), 400
            
            temp_file_path = os.path.join(TEMP_DIR, f"export_{controller_uuid}.graphml")
            with open(temp_file_path, "w", encoding="utf-8") as f:
                f.write(export_content)
                
            controller = LTLfController(
                graphml_file=temp_file_path,
                sensor_vars=sensor_vars,
                action_vars=action_vars,
                aggressive_pruning=aggressive_pruning,
                prune=prune
            )

        with controllers_lock:
            controllers[controller_uuid] = controller

    except Exception as e:
        return jsonify({"error": f"Failed to initialize controller: {str(e)}"}), 500
    finally:
        # Clean up the temp file immediately
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception:
                pass

    return jsonify({"uuid": controller_uuid})

@app.route("/get_action", methods=["POST"])
def get_action():
    data = request.json or {}
    uid = data.get("uuid") or request.args.get("uuid")
    sensors = data.get("sensors", {})

    if not uid:
        return jsonify({"error": "UUID is required"}), 400

    with controllers_lock:
        controller = controllers.get(uid)

    if not controller:
        return jsonify({"error": f"Controller with UUID '{uid}' not found"}), 404

    try:
        possible_actions = controller.get_possible_action(sensors)
        if possible_actions:
            chosen_action = random.choice(possible_actions)
            transitioned = controller.choose_action(chosen_action)
        else:
            chosen_action = "idle"
            transitioned = False

        return jsonify({
            "action": chosen_action,
            "transitioned": transitioned,
            "current_state": controller._current_state
        })
    except Exception as e:
        return jsonify({"error": f"Failed to retrieve action: {str(e)}"}), 500

@app.route("/close", methods=["GET"])
@app.route("/close/<uid>", methods=["GET"])
def close_controller(uid=None):
    uid = uid or request.args.get("uuid")
    if not uid:
        return jsonify({"error": "UUID parameter is required"}), 400

    with controllers_lock:
        if uid in controllers:
            del controllers[uid]
            return jsonify({"status": "closed", "uuid": uid})
        else:
            return jsonify({"error": f"Controller with UUID '{uid}' not found"}), 404

@app.route("/export", methods=["GET"])
@app.route("/export/<uid>", methods=["GET"])
def export_controller(uid=None):
    uid = uid or request.args.get("uuid")
    if not uid:
        return jsonify({"error": "UUID parameter is required"}), 400

    with controllers_lock:
        controller = controllers.get(uid)

    if not controller:
        return jsonify({"error": f"Controller with UUID '{uid}' not found"}), 404

    temp_export_path = os.path.join(TEMP_DIR, f"export_{uuid.uuid4()}.graphml")
    try:
        controller.export_graph(temp_export_path)
        with open(temp_export_path, "r", encoding="utf-8") as f:
            export_content = f.read()
    except Exception as e:
        return jsonify({"error": f"Failed to export controller: {str(e)}"}), 500
    finally:
        if os.path.exists(temp_export_path):
            try:
                os.remove(temp_export_path)
            except Exception:
                pass

    return jsonify({
        "uuid": uid,
        "export": export_content
    })

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
