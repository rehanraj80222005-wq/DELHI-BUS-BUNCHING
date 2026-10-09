import os
from pathlib import Path
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent

@dataclass(frozen=True)
class PathConfig:
    project_root: Path = PROJECT_ROOT
    data_dir: Path = PROJECT_ROOT / os.getenv("DATA_DIR", "data")
    raw_dir: Path = data_dir / "raw"
    processed_dir: Path = data_dir / "processed"
    features_dir: Path = data_dir / "features"

@dataclass(frozen=True)
class GeoBounds:
    lat_min: float = 28.20
    lat_max: float = 29.05
    lon_min: float = 76.60
    lon_max: float = 77.60

@dataclass(frozen=True)
class GTFSConfig:
    required_files: tuple = (
        "agency.txt",
        "calendar.txt",
        "routes.txt",
        "stops.txt",
        "trips.txt",
        "stop_times.txt",
    )
    default_archive_url: str = (
        "https://files.mobilitydatabase.org/mdb-1262/mdb-1262-202406071502/mdb-1262-202406071502.zip"
    )
    realtime_url: str = "https://otd.delhi.gov.in/api/realtime/VehiclePositions.pb"
    request_timeout: int = 30

@dataclass(frozen=True)
class DatabaseConfig:
    url: str = os.getenv("DATABASE_URL", f"sqlite:///{PROJECT_ROOT}/data/delhi_transit.db")
    echo: bool = False

@dataclass(frozen=True)
class Settings:
    paths: PathConfig = PathConfig()
    geo: GeoBounds = GeoBounds()
    gtfs: GTFSConfig = GTFSConfig()
    db: DatabaseConfig = DatabaseConfig()
    api_key: str = os.getenv("OTD_API_KEY", "")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

settings = Settings()
