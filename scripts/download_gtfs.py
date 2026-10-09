import sys
import zipfile
import logging
from pathlib import Path
import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def download_static_gtfs(target_dir: Path = settings.paths.raw_dir, extract: bool = True) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    zip_path = target_dir / "delhi_gtfs_static.zip"

    url = settings.gtfs.default_archive_url
    logger.info("Downloading official Delhi static GTFS archive from: %s", url)

    response = requests.get(url, stream=True, timeout=60)
    response.raise_for_status()

    total_bytes = 0
    with open(zip_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)
                total_bytes += len(chunk)

    logger.info("Downloaded %d bytes to %s", total_bytes, zip_path)

    if extract:
        logger.info("Extracting GTFS files into: %s", target_dir)
        with zipfile.ZipFile(zip_path, "r") as archive:
            archive.extractall(target_dir)
            files = archive.namelist()
            logger.info("Extracted %d files: %s", len(files), ", ".join(files))

    return zip_path


if __name__ == "__main__":
    download_static_gtfs()
