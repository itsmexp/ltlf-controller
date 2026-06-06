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