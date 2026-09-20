"""Tests never touch the network: the app's startup bank reload is off here."""
import os

os.environ.setdefault("BANK_RELOAD_ON_START", "off")
