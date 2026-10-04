"""Select potential industrial heat sinks from EPA FRS national single file."""

import zipfile
from pathlib import Path

import pandas as pd

FRS_COLUMNS = [
    "REGISTRY_ID", "PRIMARY_NAME", "LATITUDE83", "LONGITUDE83",
    "NAICS_CODES", "SIC_CODES",
]
SECTOR_PREFIXES = {
    "food": "311", "beverage": "312", "paper": "322",
    "chemical": "325", "metal": "331",
}


def selected_codes(value: object) -> list[str]:
    if pd.isna(value):
        return []
    return [
        code for code in (part.strip() for part in str(value).split(","))
        if len(code) == 6 and code.isdigit()
        and code[:3] in SECTOR_PREFIXES.values()
    ]


def read_industrial_facilities(path: Path) -> tuple[pd.DataFrame, list[str], dict]:
    """Stream the compressed 2.7 GB CSV without extracting or altering the raw ZIP."""
    selected = []
    total_rows = 0
    with zipfile.ZipFile(path) as archive, archive.open("NATIONAL_SINGLE.CSV") as raw:
        header = pd.read_csv(raw, nrows=0).columns.tolist()
    with zipfile.ZipFile(path) as archive, archive.open("NATIONAL_SINGLE.CSV") as raw:
        chunks = pd.read_csv(
            raw, usecols=FRS_COLUMNS, dtype="string", chunksize=100_000,
            low_memory=False,
        )
        for chunk in chunks:
            total_rows += len(chunk)
            codes = chunk["NAICS_CODES"].map(selected_codes)
            kept = chunk.loc[codes.map(bool)].copy()
            kept["selected_naics_codes"] = codes.loc[kept.index].map(
                lambda parts: ", ".join(parts)
            )
            selected.append(kept)
    if not selected:
        raise ValueError("No FRS chunks found")
    facilities = pd.concat(selected, ignore_index=True).rename(
        columns={
            "REGISTRY_ID": "facility_id", "PRIMARY_NAME": "facility_name",
            "LATITUDE83": "latitude", "LONGITUDE83": "longitude",
            "NAICS_CODES": "naics_codes", "SIC_CODES": "sic_codes",
        }
    )
    facilities = facilities.dropna(subset=["facility_id"])
    facilities = facilities.drop_duplicates("facility_id", keep="first")
    for column in ("latitude", "longitude"):
        facilities[column] = pd.to_numeric(facilities[column], errors="coerce")
    for sector, prefix in SECTOR_PREFIXES.items():
        facilities[f"is_{sector}"] = facilities["selected_naics_codes"].str.split(
            ", "
        ).map(lambda parts, prefix=prefix: any(code.startswith(prefix) for code in parts))
    valid_coordinates = (facilities["latitude"].between(-90, 90) & facilities[
        "longitude"
    ].between(-180, 180)).fillna(False)
    stats = {
        "raw_rows": total_rows,
        "selected_facilities": len(facilities),
        "valid_coordinate_facilities": int(valid_coordinates.sum()),
        "missing_or_invalid_coordinate_facilities": int((~valid_coordinates).sum()),
        "sector_facilities": {
            sector: int(facilities[f"is_{sector}"].sum())
            for sector in SECTOR_PREFIXES
        },
    }
    return facilities, header, stats
