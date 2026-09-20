"""Small standard-library helpers for reproducible source acquisition."""

import argparse
import hashlib
import json
import os
import ssl
import shutil
import subprocess
from pathlib import Path
import tempfile
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
MANIFEST = RAW / "manifest.json"


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def make_url(base, params=None):
    return base + ("?" + urlencode(params) if params else "")


def fetch(url):
    """Retry transient failures; raise immediately for permanent HTTP errors."""
    # Prefer the system HTTPS transport when available. It uses the machine's
    # trusted certificate configuration; certificate verification stays enabled.
    if shutil.which("curl"):
        result = subprocess.run(
            ["curl", "--fail-with-body", "--location", "--silent", "--show-error",
             "--retry", "3", "--max-time", "90", url],
            capture_output=True,
        )
        if result.returncode:
            raise RuntimeError(f"Download failed: {url}\n{result.stderr.decode(errors='replace')}\n"
                               f"{result.stdout[:500].decode(errors='replace')}")
        return result.stdout
    # A portable CA bundle also works with macOS Python installations whose
    # optional system-certificate setup has not been run. TLS stays verified.
    try:
        import certifi
    except ImportError:
        context = ssl.create_default_context()
    else:
        context = ssl.create_default_context(cafile=certifi.where())
    for attempt in range(4):
        try:
            request = Request(url, headers={"User-Agent": "StrokeAccessCourseProject/1.0"})
            with urlopen(request, timeout=90, context=context) as response:
                return response.read()
        except (HTTPError, URLError, TimeoutError) as error:
            if isinstance(error, URLError) and isinstance(error.reason, ssl.SSLCertVerificationError):
                raise RuntimeError("HTTPS certificate validation failed. Install requirements.txt (certifi) or configure your trusted CA certificates.") from error
            if isinstance(error, HTTPError) and error.code not in {429, 500, 502, 503, 504}:
                raise
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)


def json_bytes(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def read_manifest():
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text())
    return {"schema_version": 1, "sources": {}}


def use_cached(source_id, refresh):
    entry = read_manifest()["sources"].get(source_id)
    if refresh or entry is None:
        return False
    for name, metadata in entry["files"].items():
        path = RAW / name
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != metadata["sha256"]:
            raise ValueError(f"Missing or modified snapshot: {path}. Restore it or use --refresh.")
    print(f"Using verified committed snapshot: {source_id}")
    return True


def save_snapshot(source_id, files, metadata):
    """Prepare every file before replacing inputs; replace manifest last."""
    RAW.mkdir(parents=True, exist_ok=True)
    manifest = read_manifest()
    metadata = dict(metadata, retrieved_at_utc=timestamp(), files={})
    with tempfile.TemporaryDirectory(prefix=".download-", dir=RAW) as temp:
        for name, payload in files.items():
            (Path(temp) / name).write_bytes(payload)
            metadata["files"][name] = {
                "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()
            }
        manifest["sources"][source_id] = metadata
        (Path(temp) / "manifest.json").write_bytes(json_bytes(manifest))
        for name in files:
            os.replace(Path(temp) / name, RAW / name)
        os.replace(Path(temp) / "manifest.json", MANIFEST)
    print(f"Saved {source_id}: " + ", ".join(files))


def arguments(description):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--refresh", action="store_true", help="Replace this source snapshot.")
    return parser.parse_args()
