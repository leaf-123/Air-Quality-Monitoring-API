# models
# classes using Pydantic
# model_configs used to provide examples (for user to see)

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel

# ingest: request body for POST /ingest
class IngestRequest(BaseModel):
    sensor_id: str
    readings: dict[str, float]

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "sensor_id": "sensor_amsterdam_001",
                    "readings": {"pm25": 12.3, "pm10": 25.1, "no2": 18.0, "o3": 40.2}
                }
            ]
        }
    }

# ingest: response body for POST /ingest
class IngestResponse(BaseModel):
    status: str
    message: str
    sensor_id: str
    timestamp: datetime

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "success",
                    "message": "Reading ingested",
                    "sensor_id": "sensor_amsterdam_001",
                    "timestamp": "2025-12-22T15:20:00Z"
                }
            ]
        }
    }

# status: response body for GET /status
class StatusResponse(BaseModel):
    status: str
    uptime_seconds: float
    active_sensors: int
    total_readings: int
    last_update: datetime | None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "healthy",
                    "uptime_seconds": 1234.56,
                    "active_sensors": 3,
                    "total_readings": 120,
                    "last_update": "2025-12-22T15:19:00Z"
                }
            ]
        }
    }

# errors: JSON error wrapper
# provide details about errors (user-friendly)
class DetailError(BaseModel):
    detail: str

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"detail": "Sensor fake_sensor is not authorized"},
                {"detail": "readings must be a non-empty dict"}
            ]
        }
    }

# history: a timestamped measurement row
# nullable pollutant values after cleaning, coersion
class HistoryPoint(BaseModel):
    timestamp: datetime
    pm25: float | None = None
    pm10: float | None = None
    no2: float | None = None
    o3: float | None = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "timestamp": "2025-12-22T15:00:00Z",
                    "pm25": 12.3,
                    "pm10": 25.1,
                    "no2": 18.0,
                    "o3": 40.2
                },
                {
                    "timestamp": "2025-12-22T16:00:00Z",
                    "pm25": None,
                    "pm10": 30.0,
                    "no2": None,
                    "o3": 35.0
                }
            ]
        }
    }

# history: response body for GET /history/{sensor_id}
class HistoryResponse(BaseModel):
    sensor_id: str
    points: list[HistoryPoint]

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "sensor_id": "sensor_amsterdam_001",
                    "points": [
                        {
                            "timestamp": "2025-12-22T15:00:00Z",
                            "pm25": 12.3,
                            "pm10": 25.1,
                            "no2": 18.0,
                            "o3": 40.2
                        },
                        {
                            "timestamp": "2025-12-22T16:00:00Z",
                            "pm25": 14.0,
                            "pm10": 28.0,
                            "no2": 17.0,
                            "o3": 42.0
                        }
                    ]
                }
            ]
        }
    }

# distribution: an aggregated row for a province
class DistributionRow(BaseModel):
    province: str
    level: str
    count: int
    percent: float

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"province": "North Holland", "level": "safe", "count": 1200, "percent": 64.2},
                {"province": "North Holland", "level": "moderate", "count": 500, "percent": 26.8}
            ]
        }
    }

# distribution: response body for GET /distribution/{year}/{month}
class DistributionResponse(BaseModel):
    year: int
    month: int
    pollutant: str
    rows: list[DistributionRow]

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "year": 2024,
                    "month": 1,
                    "pollutant": "pm25",
                    "rows": [
                        {"province": "North Holland", "level": "safe", "count": 1200, "percent": 64.2},
                        {"province": "North Holland", "level": "moderate", "count": 500, "percent": 26.8},
                        {"province": "North Holland", "level": "danger", "count": 150, "percent": 8.0},
                        {"province": "North Holland", "level": "extreme", "count": 20, "percent": 1.0}
                    ]
                }
            ]
        }
    }

# models for aggregation, summary endpoints

# aggregation: summary statistics for a pollutant, for filtered time window
class PollutantStats(BaseModel):
    count: int
    mean: float | None = None
    median: float | None = None
    min: float | None = None
    max: float | None = None
    std: float | None = None


# aggregation: response body for GET /summary/{sensor_id}
class SummaryResponse(BaseModel):
    sensor_id: str

    # actual data coverage after filtering
    start: datetime | None = None
    end: datetime | None = None

    # statistics per pollutant
    stats: dict[str, PollutantStats]

# aggregation: a daily aggregate row
class DailyAggRow(BaseModel):
    date: str  # YYYY-MM-DD (keep JSON simple + stable)
    count: int
    mean: float | None = None
    min: float | None = None
    max: float | None = None

# aggregation: response body for GET /daily/{sensor_id}
class DailyAggResponse(BaseModel):
    sensor_id: str
    pollutant: str
    rows: list[DailyAggRow]

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "sensor_id": "sensor_amsterdam_001",
                    "pollutant": "pm25",
                    "rows": [
                        {"date": "2025-12-20", "count": 24, "mean": 10.2, "min": 4.0, "max": 22.0},
                        {"date": "2025-12-21", "count": 24, "mean": 11.1, "min": 5.0, "max": 25.0}
                    ]
                }
            ]
        }
    }