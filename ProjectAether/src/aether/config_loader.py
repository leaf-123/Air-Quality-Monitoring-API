# config loader
    # module for loading sensors.json & WKT parsing
    # use only Regular Expressions
    # extract lat, long using named capture groups
    # validate coordinate ranges (-180 to 180 for lon, -90 to 90 for lat)
    # log, discard sensors with invalid WKT (don’t crash)

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any
from typing import TypedDict

logger = logging.getLogger(__name__)

# required pattern: named groups + ignorecase + whitespace handling
# only Regular Expressions
# todo: try with query?
WKT_POINT_PATTERN = re.compile(
    r"POINT\s*\(\s*(?P<lon>-?\d+\.?\d*)\s+(?P<lat>-?\d+\.?\d*)\s*\)",
    re.IGNORECASE,
)

def load_json(path: str | Path) -> dict[str, Any] | list[Any]:
    """Load a JSON file. Allow loading of dict or list JSON roots."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def parse_wkt_point(wkt: str) -> tuple[float, float] | None:
    """
    Parse 'POINT(lon lat)' using regex named groups.
    Return (lon, lat) if valid; otherwise None.
    """
    match = WKT_POINT_PATTERN.match(wkt.strip())
    if match is None:
        return None

    lon = float(match.group("lon"))
    lat = float(match.group("lat"))

    # validate ranges
    if not (-180.0 <= lon <= 180.0):
        return None
    if not (-90.0 <= lat <= 90.0):
        return None

    return lon, lat

# apply parsing to all sensors

# unused: remove (maybe need later?)
# class RawSensor(TypedDict):
#     id: str
#     location: str
#     metadata: dict[str, Any]

def load_sensors(sensors_path: str | Path) -> list[dict[str, Any]]:
    """
    Loads sensors.json (a list of objects) and returns only valid sensors.
    Adds latitude/longitude fields derived from WKT.
    """
    raw = load_json(sensors_path)

    if not isinstance(raw, list):
        raise ValueError("sensors.json must be a JSON array (list of sensor objects).")

    valid_sensors: list[dict[str, Any]] = []

    for item in raw:
        # minimal structural checks
        sensor_id = item.get("id")
        location = item.get("location")

        if not isinstance(sensor_id, str) or not isinstance(location, str):
            logger.warning("Discarding sensor with missing id/location: %r", item)
            continue

        parsed = parse_wkt_point(location)
        if parsed is None:
            logger.warning("Discarding sensor %s due to invalid WKT: %s", sensor_id, location)
            continue

        lon, lat = parsed
        item["longitude"] = lon
        item["latitude"] = lat
        valid_sensors.append(item)

    logger.info("Loaded %d valid sensors from %s", len(valid_sensors), sensors_path)
    return valid_sensors