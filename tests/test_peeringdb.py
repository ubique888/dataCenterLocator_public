import json

import pandas as pd
import pytest

from datetime import datetime, timezone

from scripts.fetch_peeringdb import (
    HTTPResult,
    RetryDeferred,
    _split_curl_response,
    collect_facility_pages,
    fetch_snapshot,
    fetch_with_retry,
)
from src.processing.peeringdb import normalize_peering_facilities


def record(**overrides):
    value = {
        "id": 41,
        "name": "Northern Exchange",
        "country": "US",
        "state": "VA",
        "city": "Ashburn",
        "latitude": 39.0,
        "longitude": -77.0,
        "status": "ok",
        "ix_count": 2,
        "net_count": 14,
        "updated": "2026-10-01T12:00:00Z",
    }
    value.update(overrides)
    return value


def test_keeps_valid_facility_and_nullable_network_count() -> None:
    facilities, rejected, summary = normalize_peering_facilities(
        [record(net_count=None)], "20261003T120000Z", "2026-10-03T12:00:00Z"
    )

    assert len(facilities) == 1
    row = facilities.iloc[0]
    assert row.facility_id == 41
    assert row.network_count is pd.NA or pd.isna(row.network_count)
    assert row.ix_count == 2
    assert row.snapshot_id == "20261003T120000Z"
    assert rejected.empty
    assert summary["eligible_count"] == 1
    assert summary["network_count_missing"] == 1


def test_missing_network_count_field_keeps_eligible_facility_with_unknown_count() -> None:
    raw_record = record()
    del raw_record["net_count"]

    facilities, rejected, summary = normalize_peering_facilities(
        [raw_record], "snapshot", "2026-10-03T12:00:00Z"
    )

    assert len(facilities) == 1
    assert pd.isna(facilities.iloc[0]["network_count"])
    assert rejected.empty
    assert summary["network_count_missing"] == 1


def test_rejects_ineligible_coordinates_country_status_and_ix_count() -> None:
    records = [
        record(id=42, latitude=0, longitude=0),
        record(id=43, country="CA"),
        record(id=44, status="deleted"),
        record(id=45, ix_count=0),
        record(id=46, latitude=float("nan")),
    ]

    facilities, rejected, summary = normalize_peering_facilities(
        records, "20261003T120000Z", "2026-10-03T12:00:00Z"
    )

    assert facilities.empty
    assert len(rejected) == 5
    assert set(rejected["rejection_reason"]) == {
        "invalid_coordinates", "not_us", "not_active", "no_ixp", "invalid_coordinates"
    }
    assert summary["rejected_count"] == 5


def test_deduplicates_identical_rows_and_rejects_conflicting_ids() -> None:
    timestamp = "2026-10-03T12:00:00Z"
    facilities, rejected, summary = normalize_peering_facilities(
        [record(), record()], "snapshot", timestamp
    )
    assert len(facilities) == 1
    assert rejected.empty
    assert summary["duplicate_rows_removed"] == 1

    with pytest.raises(ValueError, match="conflicting PeeringDB facility ID 41"):
        normalize_peering_facilities(
            [record(), record(name="Conflicting listing")], "snapshot", timestamp
        )


def test_rejects_missing_requested_fields_in_snapshot_records() -> None:
    malformed = record()
    del malformed["ix_count"]

    with pytest.raises(ValueError, match="missing required fields.*ix_count"):
        normalize_peering_facilities([malformed], "snapshot", "2026-10-03T12:00:00Z")


def response(records, status=200):
    body = json.dumps({"data": records}).encode("utf-8")
    return HTTPResult(status=status, headers={}, body=body)


def test_pages_until_a_successful_empty_page_and_uses_actual_page_length() -> None:
    calls = []
    batches = [[record(id=1), record(id=2)], [record(id=3)], []]

    def get_page(params):
        calls.append(dict(params))
        return response(batches[len(calls) - 1])

    pages = collect_facility_pages(get_page, page_limit=250)

    assert [page.count for page in pages] == [2, 1, 0]
    assert [page.parameters["skip"] for page in pages] == [0, 2, 3]
    assert all(page.parameters["limit"] == 250 for page in pages)
    assert all(page.started_at and page.ended_at for page in pages)
    assert all(page.started_at <= page.ended_at for page in pages)


def test_rejects_a_failed_page_instead_of_treating_it_as_end_of_data() -> None:
    def get_page(params):
        return response([record()], status=429)

    with pytest.raises(RuntimeError, match="HTTP 429"):
        collect_facility_pages(get_page, page_limit=250)


def test_rejects_invalid_json_shape_and_replayed_pages() -> None:
    def bad_shape(params):
        return HTTPResult(200, {}, b'{"data": {"id": 1}}')

    with pytest.raises(ValueError, match="data.*array"):
        collect_facility_pages(bad_shape, page_limit=1)

    def changed_record_schema(params):
        malformed = record()
        del malformed["ix_count"]
        return response([malformed])

    with pytest.raises(ValueError, match="missing required fields.*ix_count"):
        collect_facility_pages(changed_record_schema, page_limit=1)

    same = response([record()])
    calls = 0

    def replay(params):
        nonlocal calls
        calls += 1
        return same

    with pytest.raises(RuntimeError, match="repeated PeeringDB page"):
        collect_facility_pages(replay, page_limit=1)


def test_parses_http_headers_from_curl_and_defers_long_rate_limit() -> None:
    response_bytes = (
        b"HTTP/2 429\r\nRetry-After: 120\r\nContent-Type: application/json\r\n\r\n"
        b'{"error":"slow down"}\n__PEERINGDB_HTTP_STATUS__:429'
    )
    parsed = _split_curl_response(response_bytes)
    assert parsed.status == 429
    assert parsed.headers["retry-after"] == "120"
    assert parsed.body == b'{"error":"slow down"}'

    sleeps = []
    with pytest.raises(RetryDeferred, match="120s"):
        fetch_with_retry(
            {"skip": 0},
            request=lambda params, timeout: parsed,
            sleep=sleeps.append,
        )
    assert sleeps == []


def test_snapshot_publishes_all_pages_with_hash_manifest(tmp_path) -> None:
    responses = [[record()], []]
    calls = 0

    def request(params, timeout):
        nonlocal calls
        response_value = response(responses[calls])
        calls += 1
        return response_value

    frozen_time = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
    root = tmp_path / "snapshots"
    published = fetch_snapshot(
        root,
        page_limit=2,
        request=request,
        sleep=lambda _: None,
        now=lambda: frozen_time,
    )

    manifest = json.loads((published / "manifest.json").read_text())
    assert manifest["status"] == "ready"
    assert manifest["snapshot_id"] == "20261003T120000Z"
    assert manifest["raw_row_count"] == 1
    assert len(manifest["pages"]) == 2
    for page in manifest["pages"]:
        data = (published / page["file"]).read_bytes()
        import hashlib

        assert hashlib.sha256(data).hexdigest() == page["sha256"]
        assert page["started_at"] == frozen_time.isoformat().replace("+00:00", "Z")
        assert page["ended_at"] == frozen_time.isoformat().replace("+00:00", "Z")
    assert not (published / "checkpoint.json").exists()
    assert (published / "facilities.parquet").exists()
    assert (published / "rejected_records.csv").exists()
    assert not (root / ".incomplete").exists()


def test_snapshot_schema_change_stays_incomplete_and_never_publishes_ready(tmp_path) -> None:
    malformed = record()
    del malformed["ix_count"]
    frozen_time = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
    root = tmp_path / "snapshots"

    with pytest.raises(RuntimeError, match="incomplete.*missing required fields.*ix_count"):
        fetch_snapshot(
            root,
            request=lambda params, timeout: response([malformed]),
            sleep=lambda _: None,
            now=lambda: frozen_time,
        )

    assert not (root / "20261003T120000Z").exists()
    checkpoint = json.loads(
        (root / ".incomplete/20261003T120000Z/checkpoint.json").read_text()
    )
    assert checkpoint["status"] == "incomplete"
    assert "ix_count" in checkpoint["last_error"]
