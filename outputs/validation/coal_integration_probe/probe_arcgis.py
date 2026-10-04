"""Read-only public endpoint audit. Normal TLS verification remains enabled."""
import concurrent.futures
import json
import subprocess
import time
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parent
BOUNDARY = "https://geodata.osmre.gov/arcgis/rest/services/GeoMine/AllCoalmineOperations/MapServer/0"
BOND = "https://geodata.osmre.gov/arcgis/rest/services/GeoMine/ReclamationBondStatus/MapServer/0"
AML = "https://eamlis.osmre.gov/arcgis/rest/services/ProblemsStatus/MapServer"

def fetch(job):
    name, endpoint, params = job
    url = endpoint + "?" + urlencode(params)
    start = time.monotonic()
    result = subprocess.run(["curl", "--fail", "--silent", "--show-error", "--max-time", "50", url], capture_output=True)
    record = {"name": name, "url": url, "exit_code": result.returncode, "seconds": round(time.monotonic()-start,2), "bytes": len(result.stdout), "stderr": result.stderr.decode(errors="replace")}
    if result.returncode == 0:
        (ROOT / (name + ".json")).write_bytes(result.stdout)
        try:
            data = json.loads(result.stdout)
            record.update({"error": data.get("error"), "count": data.get("count"), "sample_rows": len(data.get("features", [])), "exceededTransferLimit": data.get("exceededTransferLimit")})
        except ValueError:
            record["parse_error"] = True
    return record

if __name__ == "__main__":
    jobs = [
        ("geomine_boundary_count", BOUNDARY+"/query", {"where":"1=1","returnCountOnly":"true","f":"json"}),
        ("geomine_boundary_sample", BOUNDARY+"/query", {"where":"1=1","outFields":"*","returnGeometry":"false","orderByFields":"objectid","resultRecordCount":1000,"f":"json"}),
        ("geomine_boundary_geometry", BOUNDARY+"/query", {"where":"1=1","outFields":"objectid,msha_id,permit_id,national_id,mine_name","returnGeometry":"true","orderByFields":"objectid","resultRecordCount":3,"outSR":4326,"f":"geojson"}),
        ("geomine_bond_count", BOND+"/query", {"where":"1=1","returnCountOnly":"true","f":"json"}),
        ("geomine_bond_sample", BOND+"/query", {"where":"1=1","outFields":"*","returnGeometry":"false","orderByFields":"objectid","resultRecordCount":100,"f":"json"}),
        ("eamlis_layer_meta", AML+"/0", {"f":"pjson"}),
        ("eamlis_table_meta", AML+"/1", {"f":"pjson"}),
        ("eamlis_problem_count", AML+"/0/query", {"where":"1=1","returnCountOnly":"true","f":"json"}),
        ("eamlis_problem_sample", AML+"/0/query", {"where":"1=1","outFields":"*","returnGeometry":"true","resultRecordCount":100,"outSR":4326,"f":"json"}),
    ]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        records=list(pool.map(fetch,jobs))
    (ROOT/"arcgis_access_results.json").write_text(json.dumps(records,indent=2))
    for row in records:
        print(json.dumps(row))
