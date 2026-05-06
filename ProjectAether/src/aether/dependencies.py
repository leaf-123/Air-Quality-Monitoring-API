# dependencies
# helps initialize
    # loading config
    # preparing historical df
    # initialize services (singletons = object created once, shared everywhere)
    # dependency injection glue (create shared services once, so they can be used by routes)

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from aether.config_loader import load_json, load_sensors
from aether.data_cleaning import DataCleaner
from aether.sensor_manager import SensorManager
from aether.sensor import SensorInfo
from aether.analytics import AnalyticsService
from aether.visualization import VisualizationService


logger = logging.getLogger(__name__)

_config: dict[str, Any] | None = None
_sensors: list[dict[str, Any]] | None = None
_historical_df: pd.DataFrame | None = None

# singleton for SensorManager
_sensor_manager: SensorManager | None = None

# singleton for AnalyticsService
_analytics_service: AnalyticsService | None = None

# singleton for VisualizationService
_visualization_service: VisualizationService | None = None


# helper: convert raw sensor config dicts to SensorInfo objects
# help to validate data
def _to_sensor_info(d: dict[str, Any]) -> SensorInfo:
    return SensorInfo(
        id=d["id"],
        location=d["location"],
        latitude=float(d["latitude"]),
        longitude=float(d["longitude"]),
        metadata=dict(d.get("metadata", {})),
    )


def initialize_services(config_path: str, sensors_path: str) -> None:
    """
    Called once at startup (lifespan). Loads config + sensors + historical data
    and stores them as singletons.
    """
    global _config, _sensors, _historical_df
    global _sensor_manager, _analytics_service, _visualization_service

    # 1) Load server config
    _config_obj = load_json(config_path)
    if not isinstance(_config_obj, dict):
        raise ValueError("server_config.json must be a JSON object (dict).")
    _config = _config_obj

    # 2) Load sensors
    _sensors = load_sensors(sensors_path)
    logger.info("Initialization: sensors loaded=%d", len(_sensors))

    # build SensorManager (registry + persistence)
    storage_file = _config.get("storage_file")
    if not isinstance(storage_file, str) or not storage_file:
        raise ValueError("server_config.json missing/invalid 'storage_file'")

    sensor_infos = [_to_sensor_info(d) for d in _sensors]

    _sensor_manager = SensorManager(sensors=sensor_infos, storage_file=storage_file)

    # hydrate persisted state on startup
    _sensor_manager.hydrate_from_storage()

    # 3) Load + clean historical data
    hist_path = _config.get("historical_data_file")
    if not isinstance(hist_path, str) or not hist_path:
        raise ValueError("server_config.json missing/invalid 'historical_data_file'")

    raw_df = pd.read_csv(hist_path)
    clean_df = DataCleaner.clean_historical_df(raw_df)

    dropped = len(raw_df) - len(clean_df)
    pct = 100.0 * dropped / max(len(raw_df), 1)

    _historical_df = clean_df

    logger.info(
        "Historical rows loaded=%d cleaned=%d dropped=%d (%.2f%%)",
        len(raw_df),
        len(clean_df),
        dropped,
        pct,
    )

    # 4) AnalyticsService
    thresholds = _config.get("thresholds")
    if not isinstance(thresholds, dict):
        raise ValueError("server_config.json missing/invalid 'thresholds'")

    _analytics_service = AnalyticsService(
        historical_df=_historical_df,
        sensor_manager=_sensor_manager,
        thresholds=thresholds,
    )
    logger.info("Analytics service initialized.")

    # 5) VisualizationService
    map_config = _config.get("map_config")
    if not isinstance(map_config, dict):
        map_config = {}

    _visualization_service = VisualizationService(
        sensor_manager=_sensor_manager,
        historical_df=_historical_df,
        thresholds=thresholds,
        map_config=map_config,
    )
    logger.info("Visualization service initialized.")


# getters
def get_config() -> dict[str, Any]:
    if _config is None:
        raise RuntimeError("Services not initialized: config is None")
    return _config


def get_sensors() -> list[dict[str, Any]]:
    if _sensors is None:
        raise RuntimeError("Services not initialized: sensors is None")
    return _sensors


def get_historical_df() -> pd.DataFrame:
    if _historical_df is None:
        raise RuntimeError("Services not initialized: historical_df is None")
    return _historical_df


def get_sensor_manager() -> SensorManager:
    if _sensor_manager is None:
        raise RuntimeError("Services not initialized: sensor_manager is None")
    return _sensor_manager


def get_analytics_service() -> AnalyticsService:
    if _analytics_service is None:
        raise RuntimeError("Services not initialized: analytics_service is None")
    return _analytics_service


def get_visualization_service() -> VisualizationService:
    if _visualization_service is None:
        raise RuntimeError("Services not initialized: visualization_service is None")
    return _visualization_service


# reset services
def reset_services() -> None:
    """Helpful for tests (Lecture 7/8 testing mindset)."""
    global _config, _sensors, _historical_df
    global _sensor_manager, _analytics_service, _visualization_service

    _config = None
    _sensors = None
    _historical_df = None
    _sensor_manager = None
    _analytics_service = None
    _visualization_service = None
