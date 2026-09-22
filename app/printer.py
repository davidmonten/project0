"""Bluetooth printing via the TiMini-Print CLI.

We deliberately do NOT reimplement the D100 Bluetooth protocol. TiMini-Print
(https://github.com/Dejniel/TiMini-Print, Apache-2.0) already ships a
verified D100 profile (Bluetooth Classic SPP, 200dpi, "tiny" protocol,
864-dot print width) with a scriptable CLI. We shell out to it instead of
importing its internal async API, whose exact class names we could not
fully verify without running on real hardware.

The exact CLI flags can vary between TiMini-Print releases, so the command
template is configurable (see data/config.json) rather than hardcoded.
Run `python timiniprint_command_line.py --help` on your Mac (inside the
TiMini-Print checkout) to confirm the flags before your first print, and
adjust `cli_args_template` in the config if needed.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / "data" / "config.json"

DEFAULT_CLI_ARGS_TEMPLATE = [
    "{file}",
    "--bluetooth",
    "{printer_name}",
    "--printer-model",
    "{printer_model}",
]


@dataclass
class PrinterConfig:
    cli_path: str = "timiniprint_command_line.py"
    printer_name: str = ""  # BT device name or MAC address, e.g. "D100-ABCD"
    printer_model: str = "d100"
    cli_args_template: list[str] = field(default_factory=lambda: list(DEFAULT_CLI_ARGS_TEMPLATE))

    @classmethod
    def load(cls) -> "PrinterConfig":
        if CONFIG_PATH.exists():
            data = json.loads(CONFIG_PATH.read_text())
            return cls(**{**cls().__dict__, **data})
        return cls()

    def save(self) -> None:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(self.__dict__, indent=2))

    def build_command(self, file_path: Path) -> list[str]:
        values = {
            "file": str(file_path),
            "printer_name": self.printer_name,
            "printer_model": self.printer_model,
        }
        args = [part.format(**values) for part in self.cli_args_template]
        if self.cli_path.endswith(".py"):
            return ["python3", self.cli_path, *args]
        return [self.cli_path, *args]


def cli_available(config: PrinterConfig) -> bool:
    if config.cli_path.endswith(".py"):
        return Path(config.cli_path).exists()
    return shutil.which(config.cli_path) is not None


def print_file(file_path: Path, config: PrinterConfig | None = None, timeout: float = 60.0) -> dict:
    config = config or PrinterConfig.load()
    if not config.printer_name:
        return {"success": False, "error": "Nessuna stampante configurata (printer_name mancante)."}
    if not cli_available(config):
        return {
            "success": False,
            "error": f"CLI TiMini-Print non trovata: '{config.cli_path}'. "
            "Installa TiMini-Print e imposta il percorso corretto nelle impostazioni.",
        }
    cmd = config.build_command(file_path)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Timeout durante la stampa (Bluetooth non risponde)."}
    except OSError as exc:
        return {"success": False, "error": f"Impossibile eseguire la CLI: {exc}"}
    return {
        "success": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "command": cmd,
    }
