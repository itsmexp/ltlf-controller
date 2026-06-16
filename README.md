# ltlController

Prerequisites
- Python 3.12
- `pip`
- MONA

Python environment setup
```bash
# create and activate a virtual environment using Python 3.12
python3.12 -m venv .venv
source .venv/bin/activate

# update packaging tools and install project dependencies
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

MONA

Install via system package manager (Debian/Ubuntu):
```bash
sudo apt update && sudo apt install mona
```


Verify MONA installation:
```bash
mona
```

## REST API Server

The project includes a REST API server to interact with the controller.

### How to Run the Server

To start the Flask development server on `http://127.0.0.1:5000`:
```bash
.venv/bin/python app.py
```

### Available Endpoints

The API is session-based. The following endpoints are available:

#### 1. `POST /initialize`
Initializes a new controller session and returns a UUID to identify it. Accepts a JSON body:
- `config` (string, optional): Raw configuration file content (e.g. from `case/semaphore.txt`).
- `export` (string, optional): Raw GraphML XML content from a previous export.
- `sensor_vars` (list of strings, optional): Required if initializing from an export.
- `action_vars` (list of strings, optional): Required if initializing from an export.
- `aggressive_pruning` (boolean, optional, default: `false`).
- `prune` (boolean, optional, default: `true`).

**Example Request:**
```json
{
  "config": "#action: ew_g, ns_g.\n#sensor: ew_det, ns_det.\n#rule:\ninitial_state(!ew_g & !ns_g).",
  "aggressive_pruning": false
}
```
**Example Response:**
```json
{
  "uuid": "b1a4f758-0240-4844-9823-675567d29b28"
}
```

#### 2. `POST /get_action`
Given the sensor values and the session UUID, returns the selected action to be performed and advances the controller state. Accepts a JSON body:
- `uuid` (string, required): The session UUID (can also be passed as query parameter `?uuid=...`).
- `sensors` (dict, required): Map of sensor variable names to boolean values.

**Example Request:**
```json
{
  "uuid": "b1a4f758-0240-4844-9823-675567d29b28",
  "sensors": {
    "ew_det": true,
    "ns_det": false
  }
}
```
**Example Response:**
```json
{
  "action": "idle",
  "transitioned": true,
  "current_state": "2"
}
```

#### 3. `GET /export/<uuid>`
Returns the serialized GraphML representation of the controller. Can also pass UUID as query parameter `/export?uuid=<uuid>`.

**Example Response:**
```json
{
  "uuid": "b1a4f758-0240-4844-9823-675567d29b28",
  "export": "<?xml version='1.0' encoding='utf-8'?>\n<graphml>...</graphml>"
}
```

#### 4. `GET /close/<uuid>`
Closes the controller session and removes it from the server memory. Can also pass UUID as query parameter `/close?uuid=<uuid>`.

**Example Response:**
```json
{
  "status": "closed",
  "uuid": "b1a4f758-0240-4844-9823-675567d29b28"
}
```
```