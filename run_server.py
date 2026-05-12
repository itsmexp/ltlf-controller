"""Run the LTLf Controller API server with Flask."""

from server.app import app


if __name__ == "__main__":
    print("[Server] Starting Flask API server")
    print("[Server] Host: 0.0.0.0")
    print("[Server] Port: 8000")
    print("[Server] Available endpoints: /health, /api/initialize, /api/get_possible_action, /api/choose_action, /api/close")
    app.run(host="0.0.0.0", port=8000, debug=False)
