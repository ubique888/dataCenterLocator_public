"""Fetch a complete, versioned, public PeeringDB facility snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Callable
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.processing.peeringdb import (
    REQUIRED_ELIGIBILITY_FIELDS,
    normalize_peering_facilities,
)

API_URL = "https://www.peeringdb.com/api/fac"
FIELDS = (
    "id,name,country,state,city,latitude,longitude,status,ix_count,net_count,updated"
)
USER_AGENT = "DataCenterLocator/1.0 (GET-only public data import)"
STATUS_MARKER = b"\n__PEERINGDB_HTTP_STATUS__:"


@dataclass(frozen=True)
class HTTPResult:
    status: int
    headers: dict[str, str]
    body: bytes


@dataclass(frozen=True)
class PageRecord:
    parameters: dict[str, str]
    status: int
    body: bytes
    count: int
    started_at: str
    ended_at: str


class RetryDeferred(RuntimeError):
    """PeeringDB asked the importer to wait longer than a short retry window."""


def _split_curl_response(output: bytes) -> HTTPResult:
    if STATUS_MARKER not in output:
        raise RuntimeError("curl response did not include an HTTP status")
    header_and_body, status_part = output.rsplit(STATUS_MARKER, 1)
    match = re.match(rb"(\d{3})\s*$", status_part)
    if not match:
        raise RuntimeError("could not parse PeeringDB HTTP status")
    status = int(match.group(1))

    cursor = 0
    final_headers: dict[str, str] = {}
    body = header_and_body
    while True:
        separator = header_and_body.find(b"\r\n\r\n", cursor)
        if separator < 0:
            break
        block = header_and_body[cursor:separator]
        if not block.startswith(b"HTTP/"):
            break
        headers: dict[str, str] = {}
        for line in block.split(b"\r\n")[1:]:
            if b":" in line:
                key, value = line.split(b":", 1)
                headers[key.decode("latin-1").strip().lower()] = value.decode(
                    "latin-1"
                ).strip()
        cursor = separator + 4
        final_headers = headers
        if not header_and_body[cursor:].startswith(b"HTTP/"):
            body = header_and_body[cursor:]
            break
    return HTTPResult(status=status, headers=final_headers, body=body)


def curl_get(params: dict[str, str], timeout: int = 30) -> HTTPResult:
    query = urlencode(params)
    url = f"{API_URL}?{query}"
    result = subprocess.run(
        [
            "curl",
            "--silent",
            "--show-error",
            "--max-time",
            str(timeout),
            "--dump-header",
            "-",
            "--write-out",
            "\n__PEERINGDB_HTTP_STATUS__:%{http_code}",
            "--user-agent",
            USER_AGENT,
            url,
        ],
        capture_output=True,
        check=False,
    )
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise ConnectionError(f"PeeringDB request failed ({result.returncode}): {detail}")
    return _split_curl_response(result.stdout)


def _retry_after_seconds(value: str | None, now: datetime) -> float | None:
    if not value:
        return None
    try:
        seconds = float(value)
        return seconds if math.isfinite(seconds) and seconds >= 0 else None
    except ValueError:
        try:
            deadline = parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            return None
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        return max(0.0, (deadline - now).total_seconds())


def fetch_with_retry(
    params: dict[str, str],
    *,
    request: Callable[[dict[str, str], int], HTTPResult] = curl_get,
    timeout: int = 30,
    attempts: int = 3,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> HTTPResult:
    """Issue a GET with bounded retries; reject auth and malformed statuses."""
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            result = request(params, timeout)
        except (ConnectionError, OSError, subprocess.SubprocessError) as error:
            last_error = error
            if attempt + 1 == attempts:
                break
            sleep(float(2**attempt))
            continue

        if result.status == 200:
            return result
        if result.status in {401, 403}:
            raise RuntimeError(f"PeeringDB rejected the public request: HTTP {result.status}")
        if result.status == 429:
            delay = _retry_after_seconds(result.headers.get("retry-after"), now())
            if delay is not None and delay > 60:
                raise RetryDeferred(f"PeeringDB Retry-After is {delay:.0f}s")
            if delay is None:
                delay = float(2**attempt)
        elif result.status >= 500:
            delay = float(2**attempt)
        else:
            raise RuntimeError(f"PeeringDB returned HTTP {result.status}")

        if attempt + 1 == attempts:
            raise RuntimeError(
                f"PeeringDB retryable HTTP {result.status} after {attempts} attempts"
            )
        sleep(delay)

    raise RuntimeError(f"PeeringDB request failed after {attempts} attempts: {last_error}")


def _response_rows(body: bytes) -> list[dict]:
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("PeeringDB response is not valid JSON") from error
    records = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(records, list):
        raise ValueError("PeeringDB response data must be an array")
    if any(not isinstance(row, dict) for row in records):
        raise ValueError("PeeringDB response data contains a non-object row")
    for row in records:
        missing_fields = REQUIRED_ELIGIBILITY_FIELDS.difference(row)
        if missing_fields:
            raise ValueError(
                "PeeringDB response row missing required fields: "
                f"{', '.join(sorted(missing_fields))}"
            )
    return records


def collect_facility_pages(
    fetch_page: Callable[[dict[str, str]], HTTPResult], page_limit: int = 250,
    max_pages: int = 1000,
    on_page: Callable[[int, PageRecord], None] | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> list[PageRecord]:
    """Fetch sequential offset pages until the service returns an empty page."""
    if not 1 <= page_limit <= 1000:
        raise ValueError("page_limit must be between 1 and 1000")
    if max_pages < 1:
        raise ValueError("max_pages must be positive")
    pages: list[PageRecord] = []
    seen_nonempty_pages: set[str] = set()
    skip = 0
    for _ in range(max_pages):
        params = {
            "country": "US",
            "status": "ok",
            "depth": "0",
            "fields": FIELDS,
            "limit": page_limit,
            "skip": skip,
        }
        started_at = clock().astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        response = fetch_page(params)
        ended_at = clock().astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        if response.status != 200:
            raise RuntimeError(f"PeeringDB HTTP {response.status}")
        records = _response_rows(response.body)
        if records:
            digest = hashlib.sha256(response.body).hexdigest()
            if digest in seen_nonempty_pages:
                raise RuntimeError("repeated PeeringDB page response")
            seen_nonempty_pages.add(digest)
        page = PageRecord(
            dict(params), response.status, response.body, len(records), started_at, ended_at
        )
        pages.append(page)
        if on_page is not None:
            on_page(len(pages) - 1, page)
        if not records:
            return pages
        skip += len(records)
    raise RuntimeError(f"PeeringDB exceeded the page safety limit ({max_pages})")


def _write_json(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def fetch_snapshot(
    output_root: Path,
    *,
    page_limit: int = 250,
    max_pages: int = 1000,
    request: Callable[[dict[str, str], int], HTTPResult] = curl_get,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> Path:
    """Fetch, validate and atomically publish one immutable raw snapshot."""
    snapshot_time = now().astimezone(timezone.utc)
    snapshot_id = snapshot_time.strftime("%Y%m%dT%H%M%SZ")
    started_at = snapshot_time.isoformat().replace("+00:00", "Z")
    output_root.mkdir(parents=True, exist_ok=True)
    final_dir = output_root / snapshot_id
    incomplete_root = output_root / ".incomplete"
    staging_dir = incomplete_root / snapshot_id
    if final_dir.exists() or staging_dir.exists():
        raise FileExistsError(f"PeeringDB snapshot already exists: {snapshot_id}")
    staging_dir.mkdir(parents=True)
    (staging_dir / "pages").mkdir()
    page_receipts: list[dict] = []
    request_count = 0

    def get_page(params: dict[str, str]) -> HTTPResult:
        nonlocal request_count
        request_count += 1
        return fetch_with_retry(
            params,
            request=request,
            timeout=30,
            attempts=3,
            sleep=sleep,
            now=now,
        )

    try:
        def save_page(index: int, page: PageRecord) -> None:
            filename = f"fac_page_{index:05d}.json"
            page_path = staging_dir / "pages" / filename
            page_path.write_bytes(page.body)
            page_receipts.append(
                {
                    "file": f"pages/{filename}",
                    "sha256": hashlib.sha256(page.body).hexdigest(),
                    "count": page.count,
                    "http_status": page.status,
                    "parameters": page.parameters,
                    "started_at": page.started_at,
                    "ended_at": page.ended_at,
                }
            )
            checkpoint = staging_dir / "checkpoint.json.tmp"
            _write_json(
                checkpoint,
                {
                    "snapshot_id": snapshot_id,
                    "pages_complete": page_receipts,
                    "request_count": request_count,
                },
            )
            os.replace(checkpoint, staging_dir / "checkpoint.json")

        pages = collect_facility_pages(
            get_page, page_limit, max_pages, on_page=save_page, clock=now
        )

        raw_records: list[dict] = []
        for page in pages:
            raw_records.extend(_response_rows(page.body))
        retrieved_at = now().astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        facilities, rejected, summary = normalize_peering_facilities(
            raw_records, snapshot_id, retrieved_at
        )
        ready_manifest = {
            "schema_version": 1,
            "snapshot_id": snapshot_id,
            "status": "ready",
            "started_at": started_at,
            "completed_at": retrieved_at,
            "retrieved_at": retrieved_at,
            "request_base": API_URL,
            "raw_row_count": len(raw_records),
            "pages": page_receipts,
            "normalization": summary,
        }
        _write_json(staging_dir / "manifest.json", ready_manifest)
        facilities.to_parquet(staging_dir / "facilities.parquet", index=False)
        rejected.to_csv(staging_dir / "rejected_records.csv", index=False)
        (staging_dir / "checkpoint.json").unlink(missing_ok=True)
        if final_dir.exists():
            raise FileExistsError(f"PeeringDB snapshot already exists: {snapshot_id}")
        final_dir.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staging_dir, final_dir)
        try:
            incomplete_root.rmdir()
        except OSError:
            pass
        return final_dir
    except Exception as error:
        _write_json(
            staging_dir / "checkpoint.json",
            {
                "snapshot_id": snapshot_id,
                "status": "incomplete",
                "last_error": f"{type(error).__name__}: {error}",
                "pages_complete": page_receipts,
                "request_count": request_count,
            },
        )
        raise RuntimeError(
            f"PeeringDB snapshot is incomplete; progress retained at {staging_dir}: {error}"
        ) from error


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data/raw/peeringdb",
    )
    parser.add_argument("--limit", type=int, default=250)
    parser.add_argument("--max-pages", type=int, default=1000)
    args = parser.parse_args()
    snapshot = fetch_snapshot(
        args.output_root, page_limit=args.limit, max_pages=args.max_pages
    )
    manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
    print(
        json.dumps(
            {
                "snapshot": str(snapshot),
                "snapshot_id": manifest["snapshot_id"],
                "raw_rows": manifest["raw_row_count"],
                "eligible_facilities": manifest["normalization"]["eligible_count"],
                "rejected_rows": manifest["normalization"]["rejected_count"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
