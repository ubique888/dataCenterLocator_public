import json
import re

import pandas as pd
import pytest

from src.visualization.power_connectivity import connectivity_payload


def sites():
    return pd.DataFrame(
        {
            "site_id": pd.Series([1, 2], dtype="int64"),
            "lat": [38.0, 39.0],
            "lon": [-77.0, -76.0],
        }
    )


def metrics():
    return pd.DataFrame(
        {
            "site_id": pd.Series([1, 2], dtype="int64"),
            "substation_distance_km": [0.0, 1.609344],
            "peering_facility_id": pd.Series([10, 10], dtype="Int64"),
            "peering_facility_distance_km": [2.25, 100.0],
            "peering_facility_network_count": pd.Series([20, 20], dtype="Int64"),
            "connectivity_status": ["matched", "matched"],
            "peering_snapshot_id": ["snapshot-a", "snapshot-a"],
        }
    )


def facilities():
    return pd.DataFrame(
        {
            "facility_id": pd.Series([10, 11], dtype="int64"),
            "name": ["IXP Facility", "Unused Facility"],
            "country": ["US", "US"],
            "state": ["VA", "NY"],
            "city": ["Ashburn", "New York"],
            "latitude": [38.0, 40.7],
            "longitude": [-77.0, -74.0],
            "ix_count": pd.Series([1, 2], dtype="int64"),
            "network_count": pd.Series([20, 0], dtype="Int64"),
            "source_updated_at": ["2026-10-01T00:00:00Z", None],
            "retrieved_at": ["2026-10-03T12:00:00Z"] * 2,
            "snapshot_id": ["snapshot-a"] * 2,
        }
    )


def manifest():
    return {
        "schema_version": 1,
        "snapshot_id": "snapshot-a",
        "status": "ready",
        "retrieved_at": "2026-10-03T12:00:00Z",
    }


def test_payload_is_one_to_one_uses_same_facility_count_and_only_embeds_references():
    result = connectivity_payload(sites(), metrics(), facilities(), manifest())

    assert result["schema_version"] == 1
    assert result["meta"]["snapshot_id"] == "snapshot-a"
    assert set(result["sites"]) == {"1", "2"}
    assert result["sites"]["1"] == {
        "subKm": 0.0,
        "peerKm": 2.25,
        "peerId": 10,
        "peerNetworks": 20,
        "status": "matched",
    }
    assert set(result["facilities"]) == {"10"}
    assert result["facilities"]["10"]["url"] == "https://www.peeringdb.com/fac/10"


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda s, m, f: (s.iloc[:1], m, f), "site ID sets"),
        (lambda s, m, f: (s, pd.concat([m, m.iloc[[0]]]), f), "metrics site_id.*unique"),
        (
            lambda s, m, f: (s, m.assign(peering_facility_id=pd.Series([99, 99], dtype="Int64")), f),
            "unknown facility ID",
        ),
        (
            lambda s, m, f: (s, m.assign(peering_snapshot_id="snapshot-b"), f),
            "snapshot",
        ),
    ],
)
def test_payload_rejects_broken_relations(mutate, message):
    site_frame, metric_frame, facility_frame = mutate(sites(), metrics(), facilities())

    with pytest.raises(ValueError, match=message):
        connectivity_payload(site_frame, metric_frame, facility_frame, manifest())


def test_payload_rejects_network_count_that_does_not_match_selected_facility():
    altered = metrics().copy()
    altered.loc[0, "peering_facility_network_count"] = 21

    with pytest.raises(ValueError, match="network count.*facility dimension"):
        connectivity_payload(sites(), altered, facilities(), manifest())


def test_payload_keeps_null_network_count_and_rejects_nonfinite_json_values():
    facility_frame = facilities().iloc[[0]].copy()
    facility_frame.loc[:, "network_count"] = pd.Series([pd.NA], dtype="Int64")
    metric_frame = metrics().copy()
    metric_frame.loc[:, "peering_facility_network_count"] = pd.Series(
        [pd.NA, pd.NA], dtype="Int64"
    )
    payload = connectivity_payload(sites(), metric_frame, facility_frame, manifest())

    assert payload["sites"]["1"]["peerNetworks"] is None
    assert payload["facilities"]["10"]["networks"] is None
    assert "NaN" not in json.dumps(payload, allow_nan=False)


def test_html_escapes_untrusted_facility_name_and_old_call_remains_compatible(tmp_path):
    from src.visualization.site_explorer import build_site_explorer
    from tests.test_site_explorer import sample_sites

    facility_frame = facilities().iloc[[0]].copy()
    facility_frame.loc[:, "name"] = "</script><script>alert(1)</script>&"
    payload = connectivity_payload(sites(), metrics(), facility_frame, manifest())
    output = tmp_path / "connectivity.html"
    build_site_explorer(sample_sites(), output, connectivity=payload)
    html = output.read_text(encoding="utf-8")
    match = re.search(
        r'<script type="application/json" id="connectivity-data">(.*?)</script>',
        html,
        re.DOTALL,
    )

    assert match is not None
    parsed = json.loads(match.group(1))
    assert parsed["facilities"]["10"]["name"] == "</script><script>alert(1)</script>&"
    assert "\\u003c/script>" in match.group(1)
    assert "</script><script>alert(1)" not in html
    legacy_output = tmp_path / "legacy.html"
    build_site_explorer(sample_sites(), legacy_output)
    legacy_html = legacy_output.read_text(encoding="utf-8")
    assert '<script type="application/json" id="connectivity-data">null</script>' in legacy_html
    assert 'id="view-switch" class="view-switch" aria-label="Site analysis view" hidden' in legacy_html


def test_cli_rejects_partial_connectivity_inputs():
    import subprocess
    import sys
    from pathlib import Path

    script = Path(__file__).resolve().parents[1] / "scripts/build_site_explorer.py"
    result = subprocess.run(
        [sys.executable, str(script), "--connectivity-features", "missing.parquet"],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "provided together" in result.stderr
