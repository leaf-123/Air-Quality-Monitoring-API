# analytics
# for analyzing the data (based on cleaned data)
# data cleaning is done by data_cleaning.py

from __future__ import annotations
from typing import Any

from dataclasses import dataclass
import pandas as pd

from aether.sensor_manager import SensorManager


@dataclass
class AnalyticsService:
    historical_df: pd.DataFrame
    sensor_manager: SensorManager
    thresholds: dict[str, Any]  # optional safety

    def get_sensor_history(self, sensor_id: str) -> pd.DataFrame:
        # Ensure sensor exists/authorized
        self.sensor_manager.ensure_sensor_exists(sensor_id)

        df = self.historical_df
        out = df[df["sensor_id"] == sensor_id].sort_values("timestamp")
        return out

    def get_month_df(self, year: int, month: int) -> pd.DataFrame:
        df = self.historical_df
        mask = (df["timestamp"].dt.year == year) & (df["timestamp"].dt.month == month)
        return df[mask]
    
    # classify pollutant columns
    def _classify_series(self, s: pd.Series, safe: float, moderate: float, danger: float) -> pd.Series:
        return pd.cut(
            s,
            bins=[-float("inf"), safe, moderate, danger, float("inf")],
            labels=["safe", "moderate", "danger", "extreme"],
            right=True,
        )
    
    # pm2.5
    def classify_pm25(self, df: pd.DataFrame) -> pd.DataFrame:
        t = self.thresholds
        out = df.copy()
        out["pm25_level"] = self._classify_series(
            out["pm25"],
            safe=float(t["pm25_safe"]),
            moderate=float(t["pm25_moderate"]),
            danger=float(t["pm25_danger"]),
        )
        return out
    
    # map sensor id -> province
    def _sensor_to_province_map(self) -> dict[str, str]:
        mapping = {}
        for sensor in self.sensor_manager.get_all_sensors():
            province = sensor.metadata.get("province")
            mapping[sensor.id] = province if province is not None else "Unknown"
        return mapping
    
    def add_province(self, df: pd.DataFrame) -> pd.DataFrame:
        m = self._sensor_to_province_map()
        out = df.copy()
        out["province"] = out["sensor_id"].map(m).fillna("Unknown")
        return out

    # implement monthly distribution
    def pm25_distribution_by_province(self, year: int, month: int) -> pd.DataFrame:
        df = self.get_month_df(year, month)
        df = self.add_province(df)
        df = self.classify_pm25(df)

        # Count rows per (province, level)
        grouped = (
            df.dropna(subset=["pm25_level"])
            .groupby(["province", "pm25_level"])
            .size()
            .reset_index(name="count")
        )

        # Optional: percentages within each province
        totals = grouped.groupby("province")["count"].transform("sum")
        grouped["percent"] = (grouped["count"] / totals) * 100.0

        return grouped




