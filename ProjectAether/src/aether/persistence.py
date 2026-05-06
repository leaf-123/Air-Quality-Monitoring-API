# persistence
# stores latest sensor reading to disk (simple file-based persistence)
# according to server_config.json, storage_file is readings.json (in /data directory)

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aether.sensor import SensorReading


def load_latest_readings(storage_file: str) -> dict[str, dict[str, Any]]:
    """
    Load latest readings from JSON file.
    Returns: sensor_id -> reading_dict
    """
    path = Path(storage_file)

    # no persistence file yet -> empty state
    if not path.exists():
        return {}

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))

        # expected format: dict[sensor_id -> reading]
        if isinstance(raw, dict):
            return raw

        # unexpected but valid JSON -> ignore
        return {}

    except json.JSONDecodeError:
        # corrupt or partially written file should not crash server
        return {}


def save_latest_reading(storage_file: str, reading: SensorReading) -> None:
    """
    Update JSON file immediately with latest reading for the given sensor_id.
    """
    path = Path(storage_file)
    path.parent.mkdir(parents=True, exist_ok=True)

    # load existing persisted state
    data = load_latest_readings(storage_file)

    # update latest reading for this sensor
    data[reading.sensor_id] = reading.to_dict()

    # write back immediately
    path.write_text(
        json.dumps(data, indent=2),
        encoding="utf-8",
    )
