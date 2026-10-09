import sys
import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import settings
from src.ingestion.gtfs_loader import GTFSLoader
from src.processing.validation import GTFSValidator
from src.visualization.route_map import generate_route_map

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    print("\n--- DELHI BUS BUNCHING PREDICTOR: STATIC GTFS INSPECTION ---")
    loader = GTFSLoader(settings.paths.raw_dir)
    feed = loader.load()

    validator = GTFSValidator(feed)
    report = validator.validate()
    report.print_summary()

    print("\nTable Schema Inspection:")
    for name, df in [
        ("agency", feed.agency),
        ("calendar", feed.calendar),
        ("routes", feed.routes),
        ("stops", feed.stops),
        ("trips", feed.trips),
        ("stop_times", feed.stop_times),
    ]:
        print(f"\n[{name}.txt] ({len(df):,} rows)")
        print(f"Columns: {list(df.columns)}")
        print(df.head(2).to_string(index=False))

    # Identify Route 534 (as highlighted in project blueprint)
    candidate_route = "534"
    print(f"\nGenerating route visualization for Route '{candidate_route}'...")
    output_html = settings.paths.processed_dir / f"route_{candidate_route}_map.html"
    generate_route_map(feed, candidate_route, output_html)
    print(f"Route map generated successfully at: {output_html}")


if __name__ == "__main__":
    main()
