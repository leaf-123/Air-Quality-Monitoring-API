# Project Aether – Air Quality Monitoring API

Built as part of a university software engineering/backend development project.

## Requirements
- Python 3.10+

## Overview
Project Aether is a backend system for ingesting, cleaning, analyzing, and visualizing air-quality data through a RESTful Web API.

The system follows a layered architecture to keep responsibilities clear and manageable.

There are four key layers:

1. API layer (FastAPI)
    - Receives HTTP requests
    - Validates input using Pydantic models
    - Returns structured JSON or HTML responses

2. Domain/service layer
    - Handles business logic
    - Authorizes sensors
    - Applies ingestion rules
    - Raises domain-specific errors

3. Data layer
    - Uses Pandas to read, clean, and analyze air-quality data
    - Performs aggregation, filtering, and time-based analysis
    - Persists results to disk and restores state on startup

4. Visualization layer
    - Builds interactive HTML visualizations generated via Plotly for maps and plots
    - Separates visualization logic from data analysis

### Note about comments
- Inline comments are included to explain development decisions and debugging thought processes.
- Documentation strings (`""" """`) are used to describe modules and functionality.

---

## Features
- Sensor authorization and secure data ingestion
- Persistent storage of the latest sensor readings
- Historical data access with time filtering
- Aggregations and summaries using Pandas
- Optional downsampling and filtering in analytical endpoints (to keep large datasets manageable)
- Visualization support using interactive HTML visualizations generated via Plotly
- Automatic OpenAPI documentation

---

## Technologies Used
- Python
- FastAPI
- Pydantic
- Pandas
- Plotly (interactive HTML output)
- Pytest (API testing)

---

## Project Structure

```text
src/
└── aether/
    ├── main.py              # FastAPI app, lifespan, global exception handling
    ├── routes.py            # API route definitions
    ├── models.py            # Pydantic request/response models (DTOs)
    ├── dependencies.py      # FastAPI dependency injection & service lifecycle

    ├── sensor.py            # Sensor domain model
    ├── sensor_manager.py    # Sensor authorization & ingestion logic

    ├── persistence.py       # File-based persistence (save/load readings)
    ├── config_loader.py     # Load server & sensor configuration

    ├── analytics.py         # Pandas-based analytics & aggregations
    ├── data_cleaning.py     # Data cleaning & validation helpers

    ├── visualization.py     # Plotly visualization builders (maps & plots)

config/
├── sensors.json             # Authorized sensor definitions
├── server_config.json       # System configuration

data/
├── historical_readings.csv  # Provided historical dataset
├── readings.json            # Persistent storage for latest readings

tests/
├── conftest.py              # TestClient fixture and service reset logic
├── test_api_basic.py        # Core API tests
├── test_distribution_and_history.py
```

---

## Running the Application

1. From the project root folder, create and activate a virtual environment:

### Windows
```bash
python -m venv .venv
.venv\Scripts\activate
```

### Mac/Linux
```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install all dependencies:

```bash
pip install fastapi uvicorn pydantic pandas plotly pytest
```

3. Make sure the project root folder is open.

4. Start the FastAPI server:

```bash
python -m uvicorn aether.main:app --reload --app-dir src
```

5. Open the API documentation:

```text
http://127.0.0.1:8000/docs
```

### Optional
Can also run using the startup script from the project root (recommended for Linux/macOS):

```bash
bash run.sh
```

---

## Running Tests

- Tests are written using pytest and FastAPI TestClient, as required.

Run all tests from the project root:

```bash
python -m pytest -q
```

Test coverage includes:
- API availability and basic responses
- Authorized vs unauthorized ingestion (403)
- Invalid input handling (400)
- Missing resources (404)
- HTML visualization endpoints
- Distribution endpoint edge cases
- Tests use temporary files and reset services between runs to avoid side effects

---

## API Endpoints

### Default
- `GET /`
- `GET /sensors`

### System
- `GET /health`
- `GET /status`

### Ingestion
- `POST /ingest`

### Analytics
- `GET /history/{sensor_id}`
- `GET /summary/{sensor_id}`
- `GET /daily/{sensor_id}`
- `GET /distribution/{year}/{month}`

### Visualization
- `GET /map`

*These are additional endpoints added for learning and observability purposes:*
- health
- sensors
- summary
- daily

---

## Data Processing

Pandas is used for all analytical operations, including:

### Cleaning
- Invalid timestamps are removed
- Missing and NaN values are handled safely
- Out-of-range sensor values are filtered

### Aggregation
- Daily and monthly summaries
- Distribution statistics per month
- Sensor-level summaries

### Time filtering
- from / to datetime filters
- Month and year validation
- Optional downsampling to limit result size

---

## Error Handling

The API uses explicit error handling and HTTP status codes:

- 400 Bad Request
    - Invalid input values (e.g. month out of range)

- 403 Forbidden
    - Unauthorized sensors attempting ingestion

- 404 Not Found
    - Missing sensors or unavailable historical data

- 500 Internal Server Error
    - Unexpected processing errors (logged internally)

- Custom exceptions are raised in the domain layer and translated into HTTP responses at the API layer

---

## Documentation

- Interactive OpenAPI documentation available at `/docs`

---

## Notes

### Notes & Design Decisions
- A src/ layout is used to keep application code isolated from configuration and tests
- Dependency injection is centralized to ensure predictable startup and test isolation
- Pandas is kept out of the API layer to avoid mixing responsibilities
- Visualization endpoints return interactive HTML visualizations generated via Plotly
- Extra endpoints (health, summaries) were added to improve observability and clarity
