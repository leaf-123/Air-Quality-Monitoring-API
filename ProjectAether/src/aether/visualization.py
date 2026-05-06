# visualization
# create interactive Plotly HTML
# Keep figure-building here (routes only do input validation + filtering)

from __future__ import annotations

import json
from dataclasses import dataclass

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from aether.sensor_manager import SensorManager


@dataclass
class VisualizationService:
    sensor_manager: SensorManager
    historical_df: pd.DataFrame
    thresholds: dict[str, float]
    map_config: dict[str, object]

    # helper: classify PM2.5
    def _pm25_level(self, pm25: float | None) -> str:
        """
        Convert a PM2.5 numeric value into a discrete category used for map coloring.
        Missing values => "no_data".
        """
        if pm25 is None:
            return "no_data"

        t = self.thresholds
        safe = float(t["pm25_safe"])
        moderate = float(t["pm25_moderate"])
        danger = float(t["pm25_danger"])

        if pm25 <= safe:
            return "safe"
        if pm25 <= moderate:
            return "moderate"
        if pm25 <= danger:
            return "danger"
        return "extreme"


    # ---------- internal figure builders ----------

    # Map coloring based on PM2.5 thresholds from server_config.json
    # Classified into discrete levels so Plotly can use a stable legend + colors
    # Color remains grey until data is ingested
    def _map_figure(self) -> go.Figure:
        rows = []

        for s in self.sensor_manager.get_all_sensors():
            pm25_val: float | None = None
            ts_str: str | None = None

            # last_reading is a SensorReading object (or None)
            if s.last_reading is not None:
                raw = s.last_reading.readings.get("pm25")
                try:
                    pm25_val = float(raw) if raw is not None else None
                except (TypeError, ValueError):
                    pm25_val = None

                # last_update is a datetime (or None)
                if s.last_update is not None:
                    ts_str = s.last_update.isoformat()

            rows.append(
                {
                    "sensor_id": s.id,
                    "location": s.location,
                    "latitude": s.latitude,
                    "longitude": s.longitude,
                    "pm25": pm25_val,
                    "last_update": ts_str,
                    "pm25_level": self._pm25_level(pm25_val),
                }
            )

        df = pd.DataFrame(rows)

        # map needs numeric lat/lon, not missing
        df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
        df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
        df = df.dropna(subset=["latitude", "longitude"])

        if df.empty:
            fig = go.Figure()
            fig.update_layout(title="No valid sensor coordinates available for map.")
            return fig

        # pull map settings from config, fallback to safe defaults
        zoom = float(self.map_config.get("default_zoom", 5))
        style = str(self.map_config.get("map_style", "open-street-map"))

        # discrete colors (requirement: green/yellow/orange/red, gray if no data)
        color_map = {
            "safe": "green",
            "moderate": "yellow",
            "danger": "orange",
            "extreme": "red",
            "no_data": "gray",
        }

        fig = px.scatter_map(
            df,
            lat="latitude",
            lon="longitude",
            hover_name="sensor_id",
            hover_data={
                "location": True,
                "pm25": True,
                "pm25_level": True,
                "last_update": True,
                "latitude": True,
                "longitude": True,
            },
            color="pm25_level",
            color_discrete_map=color_map,
            zoom=zoom,
            height=650,
            title="Aether Sensors - Real-time Dashboard",
        )

        # style from config (default: open-street-map no token)
        fig.update_layout(map_style=style)
        return fig


    def _timeseries_figure(self, df: pd.DataFrame, sensor_id: str) -> go.Figure:
        """
        Build multi-trace time series figure for pm25/pm10/no2/o3.
        df is expected to already be filtered/downsampled by routes.
        """
        fig = go.Figure()

        if df is None or df.empty:
            fig.update_layout(title=f"No historical data for {sensor_id}")
            return fig

        if "timestamp" not in df.columns:
            fig.update_layout(title="Missing 'timestamp' column")
            return fig

        # Ensure safe conversions
        sdf = df.copy()
        sdf["timestamp"] = pd.to_datetime(sdf["timestamp"], errors="coerce", utc=True)
        sdf = sdf.dropna(subset=["timestamp"]).sort_values("timestamp")

        pollutants = ["pm25", "pm10", "no2", "o3"]
        has_any = False

        for p in pollutants:
            if p not in sdf.columns:
                continue
            y = pd.to_numeric(sdf[p], errors="coerce")
            if y.dropna().empty:
                continue
            has_any = True
            fig.add_trace(
                go.Scatter(
                    x=sdf["timestamp"],
                    y=y,
                    mode="lines",
                    name=p.upper(),
                )
            )

        if not has_any:
            fig.update_layout(title=f"No valid pollutant values to plot for {sensor_id}")
            return fig

        fig.update_layout(
            title=f"Air Quality Time Series - {sensor_id}",
            height=600,
            hovermode="x unified",
            xaxis=dict(
                title="Time",
                rangeslider=dict(visible=True),
            ),
            yaxis=dict(title="Concentration"),
        )
        return fig

    def _distribution_figure(self, df: pd.DataFrame, year: int, month: int) -> go.Figure:
        """
        df should be the grouped output from analytics.pm25_distribution_by_province:
        columns: province, pm25_level, count, percent
        """
        if df is None or df.empty:
            fig = go.Figure()
            fig.update_layout(title=f"No distribution data for {year}-{month:02d}")
            return fig

        required = {"province", "pm25_level"}
        if not required.issubset(set(df.columns)):
            fig = go.Figure()
            fig.update_layout(title="Missing required columns for distribution chart")
            return fig

        d = df.copy()
        # Prefer percent if present; else fall back to count with normalization by plotly
        if "percent" in d.columns:
            d["percent"] = pd.to_numeric(d["percent"], errors="coerce").fillna(0.0)
            y_col = "percent"
            title = f"PM2.5 Level Distribution by Province ({year}-{month:02d})"
            fig = px.bar(
                d,
                x="province",
                y=y_col,
                color="pm25_level",
                barmode="stack",
                title=title,
                labels={"pm25_level": "PM2.5 Level", "percent": "Percent"},
                text="percent",  # show % values in bars
            )

            # Show % labels inside each stacked segment (1 decimal)
            fig.update_traces(texttemplate="%{text:.1f}%", textposition="inside")
            fig.update_layout(yaxis=dict(range=[0, 100], title="Percent"))
            
        else:
            # If no percent column, plot counts but normalize to percent
            if "count" not in d.columns:
                d["count"] = 1
            d["count"] = pd.to_numeric(d["count"], errors="coerce").fillna(0.0)
            title = f"PM2.5 Level Distribution by Province ({year}-{month:02d})"
            fig = px.bar(
                d,
                x="province",
                y="count",
                color="pm25_level",
                barmode="stack",
                title=title,
                labels={"pm25_level": "PM2.5 Level", "count": "Count"},
            )
            fig.update_layout(barnorm="percent", yaxis_title="Percent")

        fig.update_layout(height=600, xaxis_title="Province")
        return fig

    # ---------- JSON endpoints ----------

    def build_sensor_map(self) -> dict:
        fig = self._map_figure()
        # return JSON-safe dict
        return json.loads(fig.to_json())

    def build_sensor_pm25_timeseries(self, sensor_id: str) -> dict:
        # Ensure sensor exists
        self.sensor_manager.ensure_sensor_exists(sensor_id)

        df = self.historical_df
        if df.empty:
            return {"message": "Historical dataset is empty."}

        # Guard missing columns
        if "sensor_id" not in df.columns or "timestamp" not in df.columns or "pm25" not in df.columns:
            return {"message": "Missing required columns for pm25 plot."}

        sdf = df[df["sensor_id"] == sensor_id].copy()

        # Keep conversions safe
        sdf["timestamp"] = pd.to_datetime(sdf["timestamp"], errors="coerce", utc=True)
        sdf["pm25"] = pd.to_numeric(sdf["pm25"], errors="coerce")
        sdf = sdf.dropna(subset=["timestamp"]).sort_values("timestamp")

        if sdf["pm25"].dropna().empty:
            return {"message": f"No valid pm25 values to plot for sensor_id={sensor_id}"}

        fig = px.line(
            sdf,
            x="timestamp",
            y="pm25",
            title=f"PM2.5 History - {sensor_id}",
        )
        fig.update_layout(height=500)

        return json.loads(fig.to_json())

    # ---------- HTML endpoints ----------

    def build_sensor_map_html(self) -> str:
        fig = self._map_figure()
        return fig.to_html(include_plotlyjs="cdn", full_html=True)

    def build_sensor_timeseries_html(self, df: pd.DataFrame, sensor_id: str) -> str:
        fig = self._timeseries_figure(df=df, sensor_id=sensor_id)
        return fig.to_html(include_plotlyjs="cdn", full_html=True)

    def build_distribution_html(self, df: pd.DataFrame, year: int, month: int) -> str:
        fig = self._distribution_figure(df=df, year=year, month=month)
        return fig.to_html(include_plotlyjs="cdn", full_html=True)
