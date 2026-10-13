"""App registry. Each app module exposes: NAME, BASE, CREDS, restore(snap), connect(), login(page), generate(), verify()."""
import importlib


def get(name):
    return importlib.import_module(f"swm.apps.{name}")
