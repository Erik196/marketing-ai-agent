"""Small reusable dashboard operations, testable without Streamlit."""

import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory

from marketpilot.analytics import CAMPAIGN_DIRECTORY, load_campaign


def save_campaign_upload(name: str, data: bytes, directory: Path = CAMPAIGN_DIRECTORY) -> str:
    if Path(name).suffix.lower() != ".csv" or not data or len(data) > 5_000_000:
        raise ValueError("Upload a nonempty CSV smaller than 5 MB.")
    directory.mkdir(parents=True, exist_ok=True)
    # Validate before accepting the file, and use a content-derived name instead of a supplied path.
    with TemporaryDirectory(dir=directory) as temporary:
        candidate = Path(temporary) / "upload.csv"
        candidate.write_bytes(data)
        load_campaign(candidate)
    filename = f"upload_{hashlib.sha256(data).hexdigest()[:16]}.csv"
    destination = directory / filename
    if destination.is_symlink():
        raise ValueError("The upload destination must not be a symlink.")
    destination.write_bytes(data)
    return filename
