import io
import zipfile
import logging
from pathlib import Path
from typing import Dict, Optional, Union
from dataclasses import dataclass
import pandas as pd

from src.config import settings

logger = logging.getLogger(__name__)

ID_DTYPES = {
    "agency_id": str,
    "route_id": str,
    "route_short_name": str,
    "route_long_name": str,
    "trip_id": str,
    "stop_id": str,
    "stop_name": str,
    "service_id": str,
    "direction_id": str,
    "shape_id": str,
}


@dataclass
class GTFSFeed:
    agency: pd.DataFrame
    calendar: pd.DataFrame
    routes: pd.DataFrame
    stops: pd.DataFrame
    trips: pd.DataFrame
    stop_times: pd.DataFrame

    def summary(self) -> Dict[str, int]:
        return {
            "agencies": len(self.agency),
            "routes": len(self.routes),
            "trips": len(self.trips),
            "stops": len(self.stops),
            "stop_times": len(self.stop_times),
        }

    def get_route(self, route_id: str) -> Optional[pd.Series]:
        matched = self.routes[self.routes["route_id"] == str(route_id)]
        return matched.iloc[0] if not matched.empty else None

    def get_route_trips(self, route_id: str) -> pd.DataFrame:
        return self.trips[self.trips["route_id"] == str(route_id)]

    def get_trip_stops(self, trip_id: str) -> pd.DataFrame:
        trip_st = self.stop_times[self.stop_times["trip_id"] == str(trip_id)]
        if trip_st.empty:
            return pd.DataFrame()
        merged = trip_st.merge(self.stops, on="stop_id", how="left")
        return merged.sort_values(by="stop_sequence")


class GTFSLoader:
    def __init__(self, data_source: Optional[Union[str, Path]] = None):
        if data_source is None:
            self.source = settings.paths.raw_dir
        else:
            self.source = Path(data_source)

    def _read_csv(self, file_source: Union[Path, io.BytesIO], filename: str) -> pd.DataFrame:
        dtypes = ID_DTYPES.copy()
        if filename == "stops.txt":
            dtypes.update({"stop_lat": float, "stop_lon": float})
        elif filename == "stop_times.txt":
            dtypes.update({"stop_sequence": int})
        
        return pd.read_csv(
            file_source,
            dtype=dtypes,
            low_memory=False,
            keep_default_na=False
        )

    def load_from_dir(self, directory: Path) -> GTFSFeed:
        logger.info("Loading GTFS feed from directory: %s", directory)
        loaded = {}
        for req in settings.gtfs.required_files:
            file_path = directory / req
            if not file_path.exists():
                raise FileNotFoundError(f"Missing required GTFS file: {file_path}")
            table_name = req.replace(".txt", "")
            loaded[table_name] = self._read_csv(file_path, req)
            logger.debug("Loaded %s with %d records", req, len(loaded[table_name]))

        return GTFSFeed(**loaded)

    def load_from_zip(self, zip_path: Path) -> GTFSFeed:
        logger.info("Loading GTFS feed from zip archive: %s", zip_path)
        if not zip_path.exists():
            raise FileNotFoundError(f"Zip archive does not exist: {zip_path}")

        loaded = {}
        with zipfile.ZipFile(zip_path, "r") as archive:
            available_names = set(archive.namelist())
            for req in settings.gtfs.required_files:
                if req not in available_names:
                    raise FileNotFoundError(f"Missing required file in archive: {req}")
                with archive.open(req) as f:
                    table_name = req.replace(".txt", "")
                    loaded[table_name] = self._read_csv(f, req)
                    logger.debug("Loaded %s from zip with %d records", req, len(loaded[table_name]))

        return GTFSFeed(**loaded)

    def load(self) -> GTFSFeed:
        if self.source.is_file() and self.source.suffix.lower() == ".zip":
            return self.load_from_zip(self.source)

        if self.source.is_dir():
            has_all_txt = all((self.source / f).exists() for f in settings.gtfs.required_files)
            if has_all_txt:
                return self.load_from_dir(self.source)

            zip_files = list(self.source.glob("*.zip"))
            if zip_files:
                return self.load_from_zip(zip_files[0])

        raise FileNotFoundError(
            f"No valid GTFS files or archives found at {self.source}. "
            f"Expected either extracted .txt files or a .zip archive."
        )
