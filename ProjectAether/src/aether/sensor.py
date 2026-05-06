# sensor
# defines SensorInfo and SensorReading data structures

from datetime import datetime
from typing import Any


class SensorReading:
    def __init__(self, sensor_id: str, readings: dict[str, Any], timestamp: datetime):
        self.sensor_id = sensor_id
        self.readings = readings
        self.timestamp = timestamp

    def to_dict(self) -> dict[str, Any]:
        return {
            "sensor_id": self.sensor_id,
            "readings": self.readings,
            "timestamp": self.timestamp.isoformat(),
        }

class SensorInfo:
    def __init__(
        self,
        id: str,
        location: str,
        latitude: float,
        longitude: float,
        metadata: dict[str, Any],
    ):
        self.id = id
        self.location = location
        self.latitude = latitude
        self.longitude = longitude
        self.metadata = metadata

        self.last_reading = None
        self.last_update = None