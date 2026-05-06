from pathlib import Path
import sys
import pytest
from fastapi.testclient import TestClient

# Add project_root/src to Python import path so `import aether` works
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

@pytest.fixture
def client(tmp_path):
    """
    TestClient fixture required by the assignment:
    - build app via create_app()
    - reset DI singletons
    - initialize services
    - yield client
    - reset again
    """
    from aether.main import create_app
    from aether.dependencies import reset_services, initialize_services

    # Use temp files so tests don't overwrite real data
    test_storage = tmp_path / "readings.json"
    test_storage.write_text("{}")

    # Copy real config files into temp dir (or build minimal ones)
    # write minimal configs here so tests are self-contained
    test_config = tmp_path / "server_config.json"
    test_sensors = tmp_path / "sensors.json"

    test_config.write_text(
        """
{
  "storage_file": "%s",
  "historical_data_file": "data/historical_readings.csv",
  "host": "0.0.0.0",
  "port": 8000,
  "thresholds": {
    "pm25_safe": 25.0,
    "pm25_moderate": 50.0,
    "pm25_danger": 75.0,
    "pm10_safe": 50.0,
    "pm10_moderate": 100.0,
    "pm10_danger": 150.0
  },
  "map_config": {"default_zoom": 7, "map_style": "open-street-map"}
}
        """ % str(test_storage).replace("\\", "\\\\")
    )

    test_sensors.write_text(
        """
[
  {
    "id": "sensor_amsterdam_001",
    "location": "POINT(4.9041 52.3676)",
    "metadata": {"region": "Amsterdam", "province": "North Holland",
                 "deployment_date": "2024-01-15", "site_type": "urban_center"}
  }
]
        """
    )

    reset_services()
    app = create_app(str(test_config), str(test_sensors))
    initialize_services(str(test_config), str(test_sensors))

    with TestClient(app) as c:
        yield c

    reset_services()
