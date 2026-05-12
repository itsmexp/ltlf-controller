from uuid import uuid4

from flask import Blueprint, jsonify, request

from .factory import build_controller_from_config

from .state import controllers, log

api_blueprint = Blueprint("api", __name__)


@api_blueprint.route("/health", methods=["GET"])
def health():
    log(f"GET /health | active_controllers={len(controllers)}")
    return jsonify({"status": "ok", "active_controllers": len(controllers)})


@api_blueprint.route("/api/initialize", methods=["POST"])
def initialize():
    try:
        data = request.get_json() or {}
        config_file = data.get("config_file")

        log(f"POST /api/initialize | config_file={config_file!r}")

        if not config_file:
            log("POST /api/initialize | missing config_file")
            return jsonify({"error": "Missing 'config_file' parameter"}), 400

        controller = build_controller_from_config(config_file)
        controller_id = str(uuid4())
        controllers[controller_id] = controller
        log(f"POST /api/initialize | created controller_id={controller_id}")
        return jsonify({"id": controller_id}), 200
    except FileNotFoundError as e:
        log(f"POST /api/initialize | file not found: {e}")
        return jsonify({"error": str(e)}), 404
    except ValueError as e:
        log(f"POST /api/initialize | invalid config: {e}")
        return jsonify({"error": str(e)}), 400


@api_blueprint.route("/api/get_possible_action", methods=["POST"])
def get_possible_action():
    data = request.get_json() or {}
    controller_id = data.get("id")
    sensors = data.get("sensors", {})

    log(f"POST /api/get_possible_action | controller_id={controller_id!r} | sensors={sensors}")

    if not controller_id or controller_id not in controllers:
        log(f"POST /api/get_possible_action | controller not found: {controller_id!r}")
        return jsonify({"error": f"Controller {controller_id} not found"}), 404

    controller = controllers[controller_id]
    try:
        valid_actions = controller.get_possible_action(sensors)
        log(f"POST /api/get_possible_action | valid_actions={valid_actions}")
        return jsonify({"valid_actions": valid_actions}), 200
    except Exception as e:
        log(f"POST /api/get_possible_action | error: {e}")
        return jsonify({"error": str(e)}), 500


@api_blueprint.route("/api/choose_action", methods=["POST"])
def choose_action():
    data = request.get_json() or {}
    controller_id = data.get("id")
    action = data.get("action")

    log(f"POST /api/choose_action | controller_id={controller_id!r} | action={action!r}")

    if not controller_id or controller_id not in controllers:
        log(f"POST /api/choose_action | controller not found: {controller_id!r}")
        return jsonify({"error": f"Controller {controller_id} not found"}), 404

    if not action:
        log("POST /api/choose_action | missing action")
        return jsonify({"error": "Missing 'action' parameter"}), 400

    controller = controllers[controller_id]
    success = controller.choose_action(action)

    if success:
        log(f"POST /api/choose_action | success | controller_id={controller_id}")
        return jsonify({
            "status": "success",
            "message": f"Transitioned successfully using action '{action}'."
        }), 200

    log(f"POST /api/choose_action | forbidden action={action!r} | controller_id={controller_id}")
    return jsonify({
        "error": f"Action '{action}' is not allowed in the current state."
    }), 403


@api_blueprint.route("/api/close", methods=["POST"])
def close():
    data = request.get_json() or {}
    controller_id = data.get("id")

    log(f"POST /api/close | controller_id={controller_id!r}")

    if not controller_id or controller_id not in controllers:
        log(f"POST /api/close | controller not found: {controller_id!r}")
        return jsonify({"error": f"Controller {controller_id} not found"}), 404

    controller = controllers.pop(controller_id)
    controller.close()

    log(f"POST /api/close | released controller_id={controller_id}")
    return jsonify({
        "status": "success",
        "message": f"Controller {controller_id} closed and released successfully."
    }), 200
