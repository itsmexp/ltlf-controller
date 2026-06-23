# ltlfController

A command-line tool for generating and serving LTLf (Linear Temporal Logic on Finite Traces) based controllers.

## Prerequisites
- Python 3.8+
- `pip`
- MONA

## MONA Installation

Install via system package manager (Debian/Ubuntu):
```bash
sudo apt update && sudo apt install mona
```

Verify MONA installation:
```bash
mona
```

## Installation

Install the CLI tool locally using `pip`. We recommend using a virtual environment:

```bash
# create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# update packaging tools and install project dependencies
pip install --upgrade pip setuptools wheel
pip install -e .
```

Alternatively, you can install the CLI globally using `pipx`:
```bash
pipx install .
```

## CLI Usage

The project is exposed via the `ltlf_controller` terminal command. 

### `generate`
Generates a controller from a configuration file and saves it locally as a portable `.ltlf` binary file.
```bash
ltlf_controller generate "case/guard.txt" --name "guard"
```

### `serve`
Starts an interactive read-evaluate loop over standard input/output. This is designed for interacting with the controller in real-time or interfacing with other software.

```bash
ltlf_controller serve
```
**Input Format:**
The server expects lines formatted as:
`name uuid sensor1, sensor2, sensor3`
- `name`: The name of the generated controller.
- `uuid`: A unique identifier for the instance. The engine efficiently loads the automaton graph once per `name` and tracks the state concurrently for different UUIDs.
- `sensors`: A comma or space-separated list of active sensors. Any sensor not listed is considered `false`.

**Output Format:**
The server will respond with the chosen action for that UUID:
`uuid action1 action2`
If no action evaluates to true ("idle"), it will only return the `uuid`.

To shut down the server, simply type `exit`.

### `list`
Lists all the generated controllers currently saved on your machine.
```bash
ltlf_controller list
```

### `help`
Shows detailed information about a generated controller, including its sensor variables, action variables, and the original rules used for generation.
```bash
ltlf_controller help "guard"
```

### `delete`
Deletes a saved controller.
```bash
ltlf_controller delete "guard"
```

### `config`
View or modify CLI configurations, such as the persistent directory where generated controllers are stored.

To view the current storage directory:
```bash
ltlf_controller config
```

To change the storage directory persistently:
```bash
ltlf_controller config --storage-dir /new/absolute/path/to/storage
```
*Note: Modifying this setting will not automatically move your existing controllers. You must move them manually.*

### `info`
Shows general project information (version, description, storage directory) and a list of all available commands.
```bash
ltlf_controller info
```

## Tools and Tests
Graphic utilities (such as dot-to-pdf conversion) and test scripts are available in the `tools/` and `tests/` directories respectively.

## Build Guides
For OS-specific compilation and deployment instructions, refer to the following guides:
- **Windows**: [Windows Build Guide](build_windows/README_windows.md)
- **Linux**: [Linux Build Guide](build_linux/README_linux.md)