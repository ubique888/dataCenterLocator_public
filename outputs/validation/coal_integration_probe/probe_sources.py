"""Read-only network probes; stores source responses separately from pipeline inputs."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent
URLS = {
    "msha_portal": "https://www.msha.gov/mine-data-retrieval-system",
    "msha_definition": "https://arlweb.msha.gov/OpenGovernmentData/DataSets/Mines_Definition_File.txt",
    "osmre_geomine": "https://geoservices.osmre.gov/arcgis/rest/services/GeoMine?f=pjson",
    "eamlis_service": "https://eamlis.osmre.gov/arcgis/rest/services/ProblemsStatus/MapServer?f=pjson",
    "sierraclub_map": "https://www.sierraclub.org/coal/coal-plant-map",
}

def probe(item):
    name, url = item
    try:
        r = requests.get(url, timeout=(10, 25))
        suffix = ".json" if "json" in r.headers.get("Content-Type", "") else ".txt"
        file = ROOT / (name + suffix)
        file.write_bytes(r.content)
        return {"name": name, "url": url, "final_url": r.url, "status": r.status_code,
                "content_type": r.headers.get("Content-Type"), "bytes": len(r.content),
                "sha256": hashlib.sha256(r.content).hexdigest(), "saved": file.name}
    except requests.RequestException as e:
        return {"name": name, "url": url, "error": str(e)}

if __name__ == "__main__":
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(probe, URLS.items()))
    (ROOT / "access_results.json").write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results, indent=2))
