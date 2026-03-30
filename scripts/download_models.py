"""Pre-descarga el modelo rembg en build time para evitar cold start."""
from rembg import new_session
import sys

model = sys.argv[1] if len(sys.argv) > 1 else "birefnet-lite"
print(f"Downloading rembg model: {model}")
session = new_session(model)
print(f"Model {model} downloaded and verified successfully")
