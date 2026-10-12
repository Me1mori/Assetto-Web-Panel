"""Paquete del backend.

Cargar el `.env` aquí (y no en `main.py`) garantiza que se ejecute **antes**
que cualquier módulo que lea variables al importarse, como `security`. Además
evita reordenar los imports de `main.py`.
"""
from backend.config import load_env_file

load_env_file()