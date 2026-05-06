# sensor_manager
# validates sensors, accepts new readings, tracks runtime sensor state

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from aether.sensor import SensorInfo, SensorReading
from aether.persistence import save_latest_reading, load_latest_readings
from aether.data_cleaning import DataCleaner


# exceptions
class UnauthorizedSensorError(Exception):
    pass


class InvalidReadingError(Exception):
    pass


# init
class SensorManager:
    def __init__(self, sensors: list[SensorInfo], storage_file: str):
        # registry: id -> SensorInfo
        self.sensors: dict[str, SensorInfo] = {s.id: s for s in sensors}
        self.storage_file = storage_file

        # runtime stats
        self.total_readings = 0
        self.start_time = datetime.now(timezone.utc)
        self.last_update: datetime | None = None

    # ingest_reading (most important method)
    def ingest_reading(self, sensor_id: str, readings: dict[str, Any]) -> SensorReading:
        # authorize sensor
        if sensor_id not in self.sensors:
            raise UnauthorizedSensorError(f"Sensor {sensor_id} is not authorized")

        # basic sanity checks (not Pandas cleaning)
        if not isinstance(readings, dict) or len(readings) == 0:
            raise InvalidReadingError("readings must be a non-empty dict")

        # Pandas-based validation (assignment requirement)
        ok, errors = DataCleaner.validate_readings(readings)
        if not ok:
            raise InvalidReadingError("; ".join(errors))

        # build reading
        now = datetime.now(timezone.utc)
        reading = SensorReading(sensor_id=sensor_id, readings=readings, timestamp=now)

        # persist immediately (file-based storage)
        save_latest_reading(self.storage_file, reading)

        # update in-memory state
        sensor = self.sensors[sensor_id]
        sensor.last_reading = reading
        sensor.last_update = now

        self.total_readings += 1
        self.last_update = now

        return reading

    def hydrate_from_storage(self) -> None:
        """
        Restore latest readings into in-memory sensor state on startup.
        This enables /status and /map to reflect persisted state after restart.
        """
        data = load_latest_readings(self.storage_file)

        # counters based on what's stored (latest per sensor)
        self.total_readings = 0
        self.last_update = None

        for sensor_id, payload in data.items():
            # ignore unknown/unauthorized sensors in persistence file
            if sensor_id not in self.sensors:
                continue

            # payload is expected to be a dict like:
            # {"sensor_id": "...", "timestamp": "...", "readings": {...}}
            ts_raw = payload.get("timestamp")
            readings = payload.get("readings", {})

            if not isinstance(readings, dict):
                continue

            # parse timestamp safely (ISO format)
            ts: datetime | None = None
            if isinstance(ts_raw, str):
                try:
                    ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                except ValueError:
                    ts = None

            # rebuild SensorReading object for consistent in-memory type
            rebuilt = SensorReading(sensor_id=sensor_id, readings=readings, timestamp=ts)

            sensor = self.sensors[sensor_id]
            sensor.last_reading = rebuilt
            sensor.last_update = ts

            self.total_readings += 1
            if ts and (self.last_update is None or ts > self.last_update):
                self.last_update = ts

    # status getters
    def get_active_sensors_count(self) -> int:
        return sum(1 for s in self.sensors.values() if s.last_reading is not None)

    def get_uptime_seconds(self) -> float:
        return (datetime.now(timezone.utc) - self.start_time).total_seconds()

    def get_status_snapshot(self) -> dict[str, Any]:
        # status is healthy or degraded
        status_str = (
            "healthy"
            if self.get_active_sensors_count() > 0 or self.total_readings > 0
            else "degraded"
        )
        return {
            "status": status_str,
            "uptime_seconds": self.get_uptime_seconds(),
            "active_sensors": self.get_active_sensors_count(),
            "total_readings": self.total_readings,
            "last_update": self.last_update,
        }

    # for map
    def get_latest_for_map(self) -> list[SensorInfo]:
        # map uses SensorInfo objects which include last_reading/last_update
        return list(self.sensors.values())

    # for analytics service
    def get_all_sensors(self) -> list[SensorInfo]:
        return list(self.sensors.values())

    # for /history/{sensor_id} and other endpoints
    def ensure_sensor_exists(self, sensor_id: str) -> None:
        if sensor_id not in self.sensors:
            raise UnauthorizedSensorError(f"Sensor {sensor_id} is not authorized")
