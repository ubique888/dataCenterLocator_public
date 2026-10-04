"""Probe official bulk and replacement service endpoints; no production writes."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent
URLS = {
    "Mines.zip": "https://arlweb.msha.gov/OpenGovernmentData/DataSets/Mines.zip",
    "geomine_boundary_meta.json": "https://geodata.osmre.gov/arcgis/rest/services/GeoMine/AllCoalmineOperations/MapServer/0?f=pjson",
    "geomine_bond_meta.json": "https://geodata.osmre.gov/arcgis/rest/services/GeoMine/ReclamationBondStatus/MapServer/0?f=pjson",
    "geomine_landuse_meta.json": "https://geodata.osmre.gov/arcgis/rest/services/GeoMine/PostMiningLandUse/MapServer/0?f=pjson",
    "amlisprod.html": "https://amlisprod.osmre.gov/",
}

def probe(item):
    name, url = item
    try:
        r = requests.get(url, timeout=(10, 30))
        (ROOT / name).write_bytes(r.content)
        return {"file": name, "url": url, "final_url": r.url, "status": r.status_code,
                "content_type": r.headers.get("Content-Type"), "last_modified": r.headers.get("Last-Modified"),
                "bytes": len(r.content), "sha256": hashlib.sha256(r.content).hexdigest()}
    except requests.RequestException as e:
        return {"file": name, "url": url, "error": str(e)}

if __name__ == "__main__":
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(probe, URLS.items()))
    (ROOT / "bulk_access_results.json").write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results, indent=2))
