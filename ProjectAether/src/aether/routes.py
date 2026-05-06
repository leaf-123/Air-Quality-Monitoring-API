# routes
# the API surface
# also validates inputs, handles errors

# analytical vs. visualization endpoints
    # Analytical endpoints (/summary, /daily) return JSON for programmatic use
    # Visualization endpoints return full HTML pages (Plotly)


from __future__ import annotations

from datetime import datetime

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse

from aether.analytics import AnalyticsService
from aether.dependencies import (
    get_analytics_service,
    get_sensor_manager,
    get_visualization_service,
)
from aether.models import (
    DailyAggResponse,
    DailyAggRow,
    DetailError,
    HistoryPoint,
    HistoryResponse,
    IngestRequest,
    IngestResponse,
    PollutantStats,
    StatusResponse,
    SummaryResponse,
)
from aether.sensor_manager import InvalidReadingError, SensorManager, UnauthorizedSensorError
from aether.visualization import VisualizationService

router = APIRouter()

# helper for timestamp filtering (for query params later)
def _apply_time_window(
    df: pd.DataFrame,
    from_ts: datetime | None,
    to_ts: datetime | None,
) -> pd.DataFrame:
    """
    Filter a DataFrame by timestamp window (inclusive).
    Expects a 'timestamp' column.
    Normalizes everything to UTC to avoid timezone comparison crashes.
    """
    if "timestamp" not in df.columns:
        return df

    # Validate semantic range first
    if from_ts is not None and to_ts is not None and from_ts > to_ts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="from_ts must be <= to_ts",
        )

    # Convert data timestamps to UTC
    # coerce = try to convert the data; if conversion fails handle w/o crashing
    ts = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)

    # Build UTC bounds
    def _to_utc_bound(dt: datetime) -> pd.Timestamp:
        if dt.tzinfo is None:
            return pd.Timestamp(dt, tz="UTC")
        return pd.Timestamp(dt).tz_convert("UTC")

    mask = pd.Series(True, index=df.index)

    if from_ts is not None:
        mask &= ts >= _to_utc_bound(from_ts)
    if to_ts is not None:
        mask &= ts <= _to_utc_bound(to_ts)

    out = df.loc[mask].copy()
    out["timestamp"] = ts.loc[mask]
    return out


# helpers for applying limits
# _normalize_pagination and _downsample_history
MAX_LIMIT = 5000  # hard cap to prevent extremely large payloads


# pagination: slices list of data (allows us to get chunks of data)
def _normalize_pagination(limit: int, offset: int) -> tuple[int, int]:
    if limit < 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="limit must be >= 1")
    if offset < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="offset must be >= 0")
    if limit > MAX_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"limit must be <= {MAX_LIMIT}",
        )
    return limit, offset


def _downsample_history(df: pd.DataFrame, downsample: str) -> pd.DataFrame:
    """
    Downsample a history DataFrame by timestamp.
    Assumes df contains a 'timestamp' column already coerced to datetime.
    """
    if downsample == "none":
        return df

    if "timestamp" not in df.columns:
        return df

    # make sure timestamp is datetime
    # already done in _apply_time_window
    ts = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
    tmp = df.copy()
    tmp["timestamp"] = ts
    tmp = tmp.dropna(subset=["timestamp"])

    tmp = tmp.set_index("timestamp").sort_index()

    # numeric columns only for resampling
    # if present, keep expected pollutants
    cols = [c for c in ["pm25", "pm10", "no2", "o3"] if c in tmp.columns]
    if not cols:
        return df

    if downsample == "hourly":
        out = tmp[cols].resample("1H").mean()
    elif downsample == "daily":
        out = tmp[cols].resample("1D").mean()
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="downsample must be one of: none, hourly, daily",
        )

    out = out.reset_index()
    return out


# tags, summary, responses added to most important endpoints

# default endpoint
# Welcome Page as HTML with navigation links
@router.get("/", response_class=HTMLResponse, tags=["system"])
def root():
    # simple HTML page
    return """
    <html>
      <head><title>Aether</title></head>
      <body>
        <h1>Aether API</h1>
        <p>Welcome. Useful links:</p>
        <ul>
          <li><a href="/docs">/docs</a> (Swagger UI)</li>
          <li><a href="/status">/status</a> (JSON system status)</li>
          <li><a href="/map">/map</a> (HTML live dashboard)</li>
          <li><a href="/history/sensor_amsterdam_001">/history/{sensor_id}</a> (HTML time series)</li>
          <li><a href="/distribution/2024/1">/distribution/{year}/{month}</a> (HTML province comparison)</li>
        </ul>
      </body>
    </html>
    """


# health endpoint (not required, but useful)
# tells us if the server is working or not
@router.get("/health", tags=["system"])
def health():
    return {"ok": True}


# status endpoint
# tells us if sensors are working correctly (healthy/degraded)
@router.get(
    "/status",
    response_model=StatusResponse,
    tags=["system"],
    summary="Get service status (SensorManager snapshot)",
)
# make sure function name is NOT status (clashes w/ status from fastapi)
def get_status(manager: SensorManager = Depends(get_sensor_manager)):
    snapshot = manager.get_status_snapshot()
    return StatusResponse(
        status=snapshot["status"],
        uptime_seconds=snapshot["uptime_seconds"],
        active_sensors=snapshot["active_sensors"],
        total_readings=snapshot["total_readings"],
        last_update=snapshot["last_update"],
    )


# /ingest endpoint (most important)
@router.post(
    "/ingest",
    response_model=IngestResponse,
    summary="Ingest a new sensor reading",
    tags=["ingestion"],
    responses={
        200: {"description": "Reading accepted"},
        400: {"model": DetailError, "description": "Invalid reading payload"},
        403: {"model": DetailError, "description": "Sensor is not authorized"},
    },
)
def ingest_reading(payload: IngestRequest, manager: SensorManager = Depends(get_sensor_manager)):
    # UnauthorizedSensorError / InvalidReadingError bubble to main.py handlers
    reading = manager.ingest_reading(sensor_id=payload.sensor_id, readings=payload.readings)

    return IngestResponse(
        status="ok",
        message="reading ingested",
        sensor_id=reading.sensor_id,
        timestamp=reading.timestamp,
    )


# optional: /sensors endpoint (read-only)
@router.get("/sensors")
def list_sensors(manager: SensorManager = Depends(get_sensor_manager)):
    return [
        {"id": s.id, "latitude": s.latitude, "longitude": s.longitude, "metadata": s.metadata}
        for s in manager.get_all_sensors()
    ]


# /history/{sensor_id}
# Fixed 500 error: Pandas Timestamp/NaN values are not JSON-serializable
# Convert timestamps to datetime, NaN -> None, and guard missing columns
# HTML output for /history/{sensor_id} (Plotly time series page)
@router.get(
    "/history/{sensor_id}",
    response_class=HTMLResponse,
    summary="Get historical readings chart for a sensor",
    tags=["analytics", "visualization"],
    responses={
        200: {"description": "HTML page with Plotly time series chart"},
        400: {"model": DetailError, "description": "Invalid query parameters"},
        403: {"model": DetailError, "description": "Sensor is not authorized"},
        404: {"model": DetailError, "description": "Sensor not found or no historical data"},
    },
)
def history(
    sensor_id: str,
    from_ts: datetime | None = Query(default=None, description="Start of time window (inclusive), ISO datetime"),
    to_ts: datetime | None = Query(default=None, description="End of time window (inclusive), ISO datetime"),
    downsample: str = Query(default="none", description="none|hourly|daily"),
    analytics: AnalyticsService = Depends(get_analytics_service),
    viz: VisualizationService = Depends(get_visualization_service),
) -> str:
    # use analytics here to validate / apply query logic consistently,
    # but return the visualization HTML

    # UnauthorizedSensorError bubbles to main.py handler
    df = analytics.get_sensor_history(sensor_id)

    # if service returns empty DF for missing sensor, treat as 404
    if df is None or df.empty:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No historical data for this sensor",
        )

    df = _apply_time_window(df, from_ts, to_ts)
    df = _downsample_history(df, downsample)

    if df.empty:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No historical data for the requested time window",
        )

    # Build HTML time-series chart (Plotly) in visualization layer
    return viz.build_sensor_timeseries_html(df=df, sensor_id=sensor_id)


# routes for aggregation, summary
# /summary/{sensor_id} and /daily/{sensor_id}
@router.get(
    "/summary/{sensor_id}",
    response_model=SummaryResponse,
    summary="Get summary statistics for a sensor's historical readings",
    tags=["analytics"],
)
def summary(
    sensor_id: str,
    from_ts: datetime | None = Query(default=None, description="Start of time window (inclusive), ISO datetime"),
    to_ts: datetime | None = Query(default=None, description="End of time window (inclusive), ISO datetime"),
    analytics: AnalyticsService = Depends(get_analytics_service),
) -> SummaryResponse:
    df = analytics.get_sensor_history(sensor_id)
    df = _apply_time_window(df, from_ts, to_ts)

    # Expect at least timestamp + some pollutant columns
    if "timestamp" not in df.columns:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Historical data missing 'timestamp'. Available columns: {list(df.columns)}",
        )

    # Standard pollutant columns (ignore if missing)
    pollutants = [c for c in ["pm25", "pm10", "no2", "o3"] if c in df.columns]

    # Ensure timestamp type
    ts = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
    start = ts.min()
    end = ts.max()

    # make sure pollutant stats are floats
    def _to_float(x):
        if x is None:
            return None
        try:
            if pd.isna(x):
                return None
        except Exception:
            pass
        return float(x)

    stats: dict[str, PollutantStats] = {}
    for p in pollutants:
        s = pd.to_numeric(df[p], errors="coerce").dropna()
        stats[p] = PollutantStats(
            count=int(s.shape[0]),
            mean=_to_float(s.mean()) if not s.empty else None,
            median=_to_float(s.median()) if not s.empty else None,
            min=_to_float(s.min()) if not s.empty else None,
            max=_to_float(s.max()) if not s.empty else None,
            std=_to_float(s.std()) if not s.empty else None,
        )

    return SummaryResponse(
        sensor_id=sensor_id,
        start=start.to_pydatetime() if pd.notna(start) else None,
        end=end.to_pydatetime() if pd.notna(end) else None,
        stats=stats,
    )


@router.get(
    "/daily/{sensor_id}",
    response_model=DailyAggResponse,
    summary="Get daily aggregates (mean/min/max) for one pollutant",
    tags=["analytics"],
)
def daily_aggregates(
    sensor_id: str,
    pollutant: str = "pm25",
    from_ts: datetime | None = Query(default=None, description="Start of time window (inclusive), ISO datetime"),
    to_ts: datetime | None = Query(default=None, description="End of time window (inclusive), ISO datetime"),
    limit: int = Query(default=365, description="Max number of rows to return"),
    offset: int = Query(default=0, description="Number of rows to skip"),
    analytics: AnalyticsService = Depends(get_analytics_service),
) -> DailyAggResponse:
    df = analytics.get_sensor_history(sensor_id)
    df = _apply_time_window(df, from_ts, to_ts)

    if "timestamp" not in df.columns:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Historical data missing 'timestamp'. Available columns: {list(df.columns)}",
        )

    allowed = [c for c in ["pm25", "pm10", "no2", "o3"] if c in df.columns]
    if pollutant not in df.columns:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"pollutant must be one of: {allowed}",
        )

    ts = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
    s = pd.to_numeric(df[pollutant], errors="coerce")

    tmp = pd.DataFrame({"timestamp": ts, "value": s}).dropna(subset=["timestamp"])
    tmp["date"] = tmp["timestamp"].dt.date

    # groupby date and compute daily aggregates
    g = (
        tmp.dropna(subset=["value"])
        .groupby("date")["value"]
        .agg(["count", "mean", "min", "max"])
        .reset_index()
    )

    rows: list[DailyAggRow] = []
    for r in g.to_dict(orient="records"):
        # date is a python date object -> ISO string YYYY-MM-DD
        date_str = r["date"].isoformat()

        def _f(x):
            return None if pd.isna(x) else float(x)

        rows.append(
            DailyAggRow(
                date=date_str,
                count=int(r["count"]),
                mean=_f(r["mean"]),
                min=_f(r["min"]),
                max=_f(r["max"]),
            )
        )

    limit, offset = _normalize_pagination(limit, offset)
    rows_page = rows[offset : offset + limit]
    return DailyAggResponse(sensor_id=sensor_id, pollutant=pollutant, rows=rows_page)


# /distribution/{year}/{month}
# HTML output for distribution (100% stacked bar chart)
@router.get(
    "/distribution/{year}/{month}",
    response_class=HTMLResponse,
    summary="Get monthly PM2.5 distribution by province (HTML chart)",
    tags=["analytics", "visualization"],
    responses={
        200: {"description": "HTML page with stacked bar distribution chart"},
        400: {"model": DetailError, "description": "Invalid year or month value"},
        403: {"model": DetailError, "description": "Sensor is not authorized"},
        404: {"model": DetailError, "description": "No data for specified period"},
    },
)
def distribution(
    year: int,
    month: int,
    analytics: AnalyticsService = Depends(get_analytics_service),
    viz: VisualizationService = Depends(get_visualization_service),
) -> str:
    if month < 1 or month > 12:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="month must be between 1 and 12",
        )

    # UnauthorizedSensorError bubbles to main.py handler
    grouped = analytics.pm25_distribution_by_province(year, month)

    if grouped is None or grouped.empty:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No distribution data for the specified period",
        )

    # Build HTML distribution chart in visualization layer
    return viz.build_distribution_html(df=grouped, year=year, month=month)


# visualization
# /map, /history, /distribution return HTML dashboards (Plotly)
@router.get(
    "/map",
    response_class=HTMLResponse,
    summary="Get real-time dashboard (HTML Plotly map)",
    tags=["visualization"],
    responses={200: {"description": "HTML page with interactive Plotly map"}},
)
def map_endpoint(viz: VisualizationService = Depends(get_visualization_service)) -> str:
    # raise RuntimeError("boom")  # NOT necessary, but used to test 500 error
    # Build full HTML using fig.to_html(..., full_html=True)
    return viz.build_sensor_map_html()
