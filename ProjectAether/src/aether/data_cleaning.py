# data_cleaning
# handles cleaning data, so it can be analyzed later (w/ analytics.py)

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class ValidationResult:
    is_valid: bool
    errors: list[str]


class DataCleaner:
    @staticmethod
    def validate_readings(readings: dict[str, Any]) -> tuple[bool, list[str]]:
        """
        Pandas-based validation for ingestion.
        Returns (ok, errors). We validate shape + numeric convertibility and basic sanity.
        (Domain models store raw data; this is only the pre-ingest check.)
        """
        errors: list[str] = []

        if not isinstance(readings, dict) or not readings:
            return False, ["readings must be a non-empty dictionary"]

        # Vectorized numeric conversion
        s = pd.Series(readings, dtype="object")
        numeric = pd.to_numeric(s, errors="coerce")

        # 1) Non-numeric / missing values
        bad_numeric = numeric.isna()
        if bad_numeric.any():
            bad_keys = s.index[bad_numeric].tolist()
            errors.append(f"Non-numeric or missing values for: {bad_keys}")

        # 2) Negative values (common sensor sanity check)
        # Only check where numeric is valid
        neg = (numeric < 0) & (~bad_numeric)
        if neg.any():
            neg_keys = s.index[neg].tolist()
            errors.append(f"Negative values not allowed for: {neg_keys}")

        ok = len(errors) == 0
        return ok, errors

    @staticmethod
    def clean_historical_df(df: pd.DataFrame) -> pd.DataFrame:
        # 1) Drop missing critical values
        df = df.dropna(subset=["sensor_id", "timestamp"])

        # 2) Parse timestamp
        df = df.assign(timestamp=pd.to_datetime(df["timestamp"], errors="coerce"))
        df = df.dropna(subset=["timestamp"])

        # 3) Remove negative pollutant values (vectorized, no loops)
        pollutant_cols = ["pm25", "pm10", "no2", "o3"]
        df[pollutant_cols] = df[pollutant_cols].apply(pd.to_numeric, errors="coerce")
        
        mask = (df[pollutant_cols] >= 0) | df[pollutant_cols].isna()
        df = df[mask.all(axis=1)]

        # 4) Filter extreme outliers (PM2.5 > 500)
        if "pm25" in df.columns:
            df = df[df["pm25"].isna() | (df["pm25"] <= 500)]

        return df


    @staticmethod
    def calculate_statistics(df: pd.DataFrame, col: str) -> dict[str, float]:
        """
        Example stats helper for later endpoints.
        """
        s = df[col].dropna()
        if s.empty:
            return {"mean": float("nan"), "median": float("nan"), "min": float("nan"), "max": float("nan"), "std": float("nan")}
        return {
            "mean": float(s.mean()),
            "median": float(s.median()),
            "min": float(s.min()),
            "max": float(s.max()),
            "std": float(s.std()),
        }
