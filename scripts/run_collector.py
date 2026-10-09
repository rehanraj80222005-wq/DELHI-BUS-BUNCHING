import sys
import time
import argparse
import logging
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import settings
from src.database.connection import init_db, get_session
from src.database.repository import TransitRepository
from src.ingestion.gtfs_loader import GTFSLoader
from src.ingestion.realtime_client import OTDRealtimeClient
from src.processing.cleaning import TelemetryCleaner
from src.processing.movement import MovementReconstructor
from src.analytics.headway import HeadwayEngine
from src.analytics.bunching import BunchingDetector

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def process_telemetry_cycle(
    client: OTDRealtimeClient,
    cleaner: TelemetryCleaner,
    reconstructor: MovementReconstructor,
    headway_engine: HeadwayEngine,
    bunching_detector: BunchingDetector,
    repo: TransitRepository,
) -> None:
    cycle_start = time.perf_counter()
    print("\n" + "=" * 65)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] RUNNING TELEMETRY INGESTION CYCLE")
    print("=" * 65)

    # 1. Fetch live GTFS-Realtime feed
    _, raw_records, _ = client.fetch_feed()
    print(f"1. Ingestion: Received {len(raw_records):,} raw vehicle observations.")

    # 2. Clean & Filter
    cleaned_records, clean_report = cleaner.clean(raw_records)
    print(f"2. Cleaning : {clean_report.valid_count:,} valid pings retained ({clean_report.out_of_bounds_dropped} out-of-bounds, {clean_report.missing_fields_dropped} invalid dropped).")

    # 3. Store raw vehicle telemetry to database
    stored_count = repo.save_vehicle_positions(cleaned_records)
    print(f"3. Storage  : Committed {stored_count:,} vehicle observations to database.")

    # 4. Movement Reconstruction & GTFS Stop Matching (sample preview)
    enhanced_records = []
    for r in cleaned_records:
        matched = reconstructor.match_trip_progress(r)
        enhanced_records.append(matched)

    # 5. Headway Calculation
    headways = headway_engine.calculate_headways_for_snapshot(enhanced_records)
    if headways:
        repo.save_headway_observations(headways)
    print(f"4. Headway  : Calculated {len(headways):,} inter-bus headway observations.")

    # 6. Bunching Detection
    events = bunching_detector.detect_bunching_events(headways)
    if events:
        repo.save_bunching_events(events)
    print(f"5. Bunching : Detected {len(events):,} active bunching episodes across Delhi network.")

    # Show top bunching events
    if events:
        severity_counts = {}
        for ev in events:
            sev = ev["severity"]
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        print("\n   Bunching Severity Breakdown:")
        for sev in ["SEVERE", "HIGH", "MODERATE", "LOW"]:
            if sev in severity_counts:
                print(f"     - {sev:<9}: {severity_counts[sev]:>3} events")

        print("\n   Sample Critical Bunching Incidents:")
        critical = [e for e in events if e["severity"] in ("SEVERE", "HIGH")][:5]
        for c in critical:
            gap_min = c["observed_headway"] / 60.0
            fol_min = (c["following_gap"] / 60.0) if c["following_gap"] else 0.0
            print(
                f"     * Route {c['route_id']:<6} | Lead: {c['leading_vehicle_id']} | "
                f"Trail: {c['trailing_vehicle_id']} | Gap: {gap_min:.1f}m (Behind: {fol_min:.1f}m) | "
                f"Severity: {c['severity']}"
            )

    elapsed = time.perf_counter() - cycle_start
    print(f"\nCycle completed in {elapsed:.2f} seconds.")
    print("=" * 65)


def main():
    parser = argparse.ArgumentParser(description="Delhi Bus Bunching Realtime Collector & Analytics Pipeline")
    parser.add_argument("--once", action="store_true", help="Run a single collection and analysis cycle then exit")
    parser.add_argument("--interval", type=int, default=30, help="Polling interval in seconds (default: 30)")
    args = parser.parse_args()

    # 1. Initialize Database Schema
    init_db()
    session = get_session()
    repo = TransitRepository(session)

    # 2. Load static GTFS feed for stop matching
    feed = None
    try:
        loader = GTFSLoader(settings.paths.raw_dir)
        feed = loader.load()
        logger.info("Loaded static GTFS: %d routes, %d stops for spatial matching.", len(feed.routes), len(feed.stops))
    except Exception as exc:
        logger.warning("Could not load static GTFS feed (%s). Running with coordinate-only matching.", exc)

    # 3. Instantiate pipeline components
    client = OTDRealtimeClient()
    cleaner = TelemetryCleaner()
    reconstructor = MovementReconstructor(feed)
    headway_engine = HeadwayEngine()
    bunching_detector = BunchingDetector()

    if args.once:
        process_telemetry_cycle(
            client, cleaner, reconstructor, headway_engine, bunching_detector, repo
        )
        return

    logger.info("Starting continuous collector daemon (interval: %d seconds). Press Ctrl+C to stop.", args.interval)
    try:
        while True:
            try:
                process_telemetry_cycle(
                    client, cleaner, reconstructor, headway_engine, bunching_detector, repo
                )
            except Exception as exc:
                logger.error("Error during telemetry cycle: %s", exc, exc_info=True)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        logger.info("Collector daemon stopped by user.")


if __name__ == "__main__":
    main()
