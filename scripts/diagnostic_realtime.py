import sys
import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import settings
from src.ingestion.realtime_client import OTDRealtimeClient
from src.ingestion.protobuf_parser import ProtobufParser

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def run_diagnostic() -> bool:
    print("=" * 65)
    print("DELHI BUS BUNCHING PREDICTOR: REALTIME API DIAGNOSTIC (PHASE 3)")
    print("=" * 65)

    if not settings.api_key:
        print("[ERROR] OTD_API_KEY is not set in .env!")
        print("Please edit .env and configure: OTD_API_KEY=your_key")
        return False

    client = OTDRealtimeClient()

    # Step 1-3: Call API, check status, download bytes
    print("\n1. Calling OTD GTFS-Realtime API endpoint...")
    print(f"   Target URL: {settings.gtfs.realtime_url}")
    print("   Authenticating using configured OTD_API_KEY from .env (hidden)...")

    try:
        raw_bytes = client.fetch_raw()
    except PermissionError as exc:
        print(f"\n[FAIL] Authentication Error: {exc}")
        return False
    except TimeoutError as exc:
        print(f"\n[FAIL] Request Timeout: {exc}")
        return False
    except ConnectionError as exc:
        print(f"\n[FAIL] Connection Error: {exc}")
        return False
    except Exception as exc:
        print(f"\n[FAIL] Unexpected Error: {exc}")
        return False

    print(f"[OK] Received {len(raw_bytes):,} protobuf bytes successfully.")

    # Step 4: Decode FeedMessage
    print("\n2. Decoding Protocol Buffer payload...")
    try:
        header, records = ProtobufParser.parse_feed_message(raw_bytes)
    except Exception as exc:
        print(f"[FAIL] Protobuf decoding error: {exc}")
        return False

    print(f"[OK] FeedMessage decoded successfully.")
    print(f"   GTFS-RT Version : {header.get('gtfs_realtime_version', 'Unknown')}")
    print(f"   Feed Header UTC : {header.get('header_datetime_utc', 'N/A')}")

    # Step 5: Entity count
    print(f"\n3. Vehicle Entity Count:")
    print(f"   Total Active Buses Reporting: {len(records):,}")

    if not records:
        print("   [WARN] No vehicle records found in current feed snapshot.")
        return True

    df = ProtobufParser.to_dataframe(records)

    # Step 6: Available VehiclePosition fields
    print(f"\n4. Available Field Population Rate (across {len(df)} vehicles):")
    for col in df.columns:
        populated = df[col].notna().sum()
        pct = (populated / len(df)) * 100
        print(f"   - {col:<22}: {populated:>5,} / {len(df)} ({pct:>5.1f}%)")

    # Step 7: Sample records
    print(f"\n5. Sample Decoded Telemetry Records (First 3 buses):")
    sample_cols = [
        "vehicle_id",
        "route_id",
        "trip_id",
        "latitude",
        "longitude",
        "speed",
        "current_status",
        "observation_time_utc",
    ]
    available_sample_cols = [c for c in sample_cols if c in df.columns]
    print(df[available_sample_cols].head(3).to_string(index=False))

    # Summary
    print("\n" + "=" * 65)
    print("PHASE 3 DIAGNOSTIC SUMMARY: ALL CHECKS PASSED")
    print("Real-time ingestion is validated and ready for DB persistence.")
    print("=" * 65)
    return True


if __name__ == "__main__":
    success = run_diagnostic()
    sys.exit(0 if success else 1)
