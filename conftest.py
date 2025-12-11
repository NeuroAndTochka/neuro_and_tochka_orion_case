from __future__ import annotations

import sys
from pathlib import Path


def _register_service_paths() -> None:
    root = Path(__file__).resolve().parent
    services_dir = root / "services"
    if not services_dir.exists():
        return
    for service_path in services_dir.iterdir():
        if not service_path.is_dir():
            continue
        if str(service_path) not in sys.path:
            sys.path.append(str(service_path))


_register_service_paths()
