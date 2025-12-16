from pathlib import Path
import os

def get_cake_root() -> Path:
    if "CAKE_ROOT" in os.environ:
        return Path(os.environ["CAKE_ROOT"]).resolve()
    return Path(__file__).resolve().parents[2]

