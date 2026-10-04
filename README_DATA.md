# Data Sources and Lineage

This file tracks source files used by the Infrastructure Inheritance & Industrial Symbiosis feature. Raw source files will be preserved under `data/raw/`; derived datasets belong under `data/processed/`. Do not overwrite source files.

## Source inventory

| Source | Planned download location | Download date | Version / file | Original fields | Fields used | Limitations |
|---|---|---|---|---|---|---|
| EPA RE-Powering Screening Dataset | [EPA mapper download page](https://www.epa.gov/re-powering/re-powering-mapper); [direct XLSX](https://www.epa.gov/system/files/documents/2023-05/re-powering-screening-dataset-2022%20Updated.xlsx) | 2026-10-03 | `re-powering-screening-dataset-2022_Updated.xlsx`; workbook says “2022 (updated 2023)”; SHA-256 `bf0ecd179a4b69640bc31ae855c1aa700546cb198189b355ed7d4ebc8770b086` | All 50 original worksheet columns are recorded in [`outputs/validation/source_columns.json`](outputs/validation/source_columns.json); exact mappings below | Cross-reference number, source site ID/name, coordinates, acreage, transmission/substation distance and voltage, road/rail distance, program, known landfill/mine flags, state, county | Screening is based on an August 2021 site snapshot. Proximity/voltage are screening attributes, not engineering interconnection guarantees. Acreage is missing for many sites. |
| EIA-860M | [EIA monthly inventory](https://www.eia.gov/electricity/data/eia860m/); [August 2026 XLSX](https://www.eia.gov/electricity/data/eia860m/xls/august_generator2026.xlsx) | 2026-10-03 | August 2026, released September 24, 2026; `august_generator2026.xlsx`; SHA-256 `b4b70abb4c217e8e2658c3bde7608a3d530e86a81279ccc572ced82a200e9f1c` | The 26 `Retired` worksheet columns are in [`outputs/validation/eia_retired_source_columns.json`](outputs/validation/eia_retired_source_columns.json); `Operating` and Puerto Rico tabs are also read | Exact `Retired` fields: `Plant ID`, `Plant Name`, `Generator ID`, `Nameplate Capacity (MW)`, `Energy Source Code`, `Retirement Year`, `Latitude`, `Longitude`; `Operating` uses `Plant ID` | Monthly inventory is preliminary. The retired list is comprehensive only for retirements since 2002. Retired nameplate capacity is a historical infrastructure-scale proxy, not currently available grid capacity. |
| EPA Facility Registry Service (FRS) | [EPA FRS geospatial download page](https://www.epa.gov/frs/geospatial-data-download-service); [national single CSV ZIP](https://ordsext.epa.gov/FLA/www3/state_files/national_single.zip) | 2026-10-03 | ZIP last modified 2026-09-08; `national_single.zip`; SHA-256 `20296ac41aca625546d84c11c1d238686ce6d65860b36760c8f1871ad8cd1093` | All 39 original columns are in [`outputs/validation/frs_source_columns.json`](outputs/validation/frs_source_columns.json) | `REGISTRY_ID`, `PRIMARY_NAME`, `LATITUDE83`, `LONGITUDE83`, `NAICS_CODES`, `SIC_CODES` | Facility presence and industry codes do not establish heat demand, willingness to participate, or a commercial waste-heat opportunity. 5,829 selected facilities lack usable coordinates. |
| EPA Clean Watersheds Needs Survey (CWNS) | [EPA 2022 CWNS national data download](https://sdwis.epa.gov/ords/sfdw_pub/r/sfdw/cwns_pub/data-download); ZIP and dictionary were downloaded using that page | 2026-10-03 | `2022CWNS_NATIONAL_Sept2026.zip` SHA-256 `395435bbf817f3ddea664170aa53fb860641326a894eceaa3190fd5c7f58ee95`; `CWNS-Database-Dictionary-January2025.xlsx` SHA-256 `e178475638879ebf089856998808528f2c583286e540096b57937257e54d7e2b` | Source columns for eight joined tables are in [`outputs/validation/cwns_source_columns.json`](outputs/validation/cwns_source_columns.json) | `CWNS_ID`, `FACILITY_ID`, `FACILITY_NAME`, `LOCATION_TYPE`, `LATITUDE`, `LONGITUDE`, `CURRENT_DESIGN_FLOW`, `CURRENT_EFFLUENT_TREATMENT_LEVEL`, `TOTAL_RES_POPULATION_2022` | 2022 survey snapshot. Flow is design capacity in million gallons per day (MGD), **not actual flow or reclaimable volume**. Location may be approximate or absent. |

## Source handling

- Record the exact official download URL, access/download date, source release or file version, and original column names when each source is acquired.
- Preserve downloaded files unchanged in the matching `data/raw/` directory.
- Record any column mapping and derived-field lineage alongside the processing code or dataset documentation.
- Do not infer missing source fields. Mark unavailable fields and their effects on downstream analysis.

## STEP 1: EPA RE-Powering mapping

The source worksheet is `RE-Powering Sites`. `Cross-Reference Number` is the unique `site_id` (190,976 unique values); the source's `Site ID` is retained as `source_site_id` because it repeats and contains both text and numeric cells. Numeric source IDs are stored as text in Parquet. `site_type` is derived only from `Known Landfill` and `Known Abandoned Mine Land` flags: a `Y` indicates a known category; other rows remain missing. `Program` is retained separately as `source_program` and is not treated as a physical site type.

| Standardized field | Exact source column | Unit / interpretation |
|---|---|---|
| `site_id` | `Cross-Reference Number` | EPA cross-reference key |
| `source_site_id` | `Site ID` | EPA/state source identifier; not unique |
| `site_name` | `Site Name` | Source name |
| `latitude`, `longitude` | `Latitude`, `Longitude` | Decimal degrees |
| `acreage` | `Acreage (Acres)` | Acres |
| `distance_to_transmission` | `Distance to Nearest Transmission Line (miles)` | Miles |
| `transmission_voltage` | `Nearest Transmission Line kV (kilovolts)` | kV |
| `transmission_status` | `Nearest Transmission Line Status` | Source's line status; retained for review |
| `distance_to_substation` | `Distance to Nearest Substation (miles)` | Miles |
| `substation_voltage` | `Nearest Substation Voltage (Volts)` | Raw reported number; source label says “Volts” although values such as 115 and 138 suggest kV. Unit must be verified before quantitative use. |
| `distance_to_road` | `Distance to Nearest Road (miles)` | Miles |
| `distance_to_rail` | `Distance to Nearest Rail (miles)` | Miles |
| `source_program` | `Program` | Managing program, not land-use type |
| `site_type` | `Known Landfill`, `Known Abandoned Mine Land` | Derived only for source `Y` flags; otherwise missing |
| `state`, `county` | `State`, `County` | Source administrative labels |

`passes_initial_filter` requires acreage ≥50 acres, transmission distance ≤3 miles, transmission voltage ≥115 kV, and substation distance ≤5 miles. All 190,976 source rows remain in `data/processed/candidate_sites.parquet`; 8,479 pass. Missing filter inputs do not pass. Exact statistics and the seeded ten-site sample are in [`outputs/validation/step1_summary.json`](outputs/validation/step1_summary.json).

The source reports 48 transmission values above 765 kV, including four passing sites. These values remain unchanged and are flagged by `transmission_voltage_review_required` for source-level review. Two substation values exceed 765 in their reported unit and are flagged separately.

The validation map uses [USGS The National Map USGSTopo tiles](https://basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer), with visible USGS attribution. [USGS terms](https://www.usgs.gov/faqs/what-are-the-terms-use-licensing-map-services-and-data-national-map) state its map services and data are public domain and have no use restrictions; the service asks products to credit the U.S. Geological Survey, National Geospatial Program. The map requires an internet connection to load this base layer. This avoids requests to `tile.openstreetmap.org`, whose [tile policy](https://operations.osmfoundation.org/policies/tiles/) requires a valid web `Referer` and does not work for a page opened directly from `file://`.

## STEP 2: retired power plant proximity

`data/processed/retired_power_sites.parquet` has one row per EIA `Plant ID`, aggregating nameplate MW from retired generators, the latest retirement year, the fuel code with the largest retired nameplate MW, and generator count. A plant is marked `fully_retired` only when its ID is absent from the same EIA-860M snapshot's `Operating` and `Operating_PR` tabs. This inventory-based flag does not establish site vacancy or reuse rights.

`data/processed/candidate_sites_power.parquet` retains every STEP 1 site and attaches its nearest fully retired plant when geodesic distance is ≤2 km. Confidence bands are ≤0.25 km `very_high`, ≤0.5 km `high`, ≤1 km `medium`, ≤2 km `low`, and otherwise `unmatched`. At 2 km, nearby but unrelated properties can match; the source coordinates are point locations, not parcel boundaries. Unmatched capacities remain missing rather than zero. The nearest match and its confidence require parcel-level review before claims of infrastructure inheritance. The exact statistics and ten sampled matches are in [`outputs/validation/step2_summary.json`](outputs/validation/step2_summary.json).

## STEP 3: infrastructure inheritance screening score

`data/processed/candidate_sites_inheritance.parquet` retains the raw acreage, retired capacity, transmission voltage/distance, substation voltage/distance, and road/rail distances. Five component utilities and `inheritance_score` are additional fields, all on 0–100 scales. Each anchor list below is linearly interpolated between points and capped at its end values, so outliers do not set the entire scale. Higher scores are better.

| Component | Utility anchors (input → score) | Combination |
|---|---|---|
| `power_legacy_component` | Former MW: 0→0, 25→25, 100→50, 500→85, 1000→100; unmatched→0 | Capacity utility × EIA proximity-confidence factor (very high 1, high .85, medium .65, low .30) × name-evidence factor. Identical EPA/EIA name word sets receive factor 1. Otherwise, a power-related descriptor in the EPA site name plus two distinctive shared words, or one shared word within 0.5 km, receives factor 1. A power-related site within 0.25 km receives .7 even without a shared name. Shared locality names alone (for example Deer Park) receive no legacy credit. Other proximity-only matches receive 0. `power_identity_evidence` preserves this classification. Name evidence is still only a screening proxy, not parcel confirmation. |
| `transmission_component` | kV: 0→0, 115→30, 138→45, 230→70, 345→90, 500→100. Miles to line: 0–0.5→100, 1→90, 2→70, 3→40, 5→0 | 65% voltage + 35% distance. Values above 500 kV are capped for scoring; source flags on unusually high voltage remain visible. |
| `substation_component` | Miles: 0–0.25→100, 0.5→90, 1→75, 2→55, 5→0 | Distance only. The source labels substation voltage “Volts” although numbers resemble kV; its unit is unverified, so it is preserved but excluded from scoring. |
| `land_component` | Acres: 0→0, 50→20, 100→40, 250→70, 500→90, 1000→100 | Acreage utility. |
| `transport_component` | Miles to road: 0–0.5→100, 1→85, 2→60, 5→20, 10→0. Miles to rail: 0–1→100, 3→75, 5→50, 10→0 | 60% road + 40% rail. |

`inheritance_score` = (30% power legacy + 25% transmission + 20% substation + 15% land + 10% transport) × (0.7 + 0.3 × name-evidence factor). The latter gate prevents grid-rich properties with no corroborated former-plant identity from dominating a legacy-focused ranking; it does not claim proof of common parcel or reuse rights. Missing source inputs propagate to null components and score, with the affected inputs in `score_missing_reason`; an unmatched power plant instead receives a defined zero power component. Ranking is restricted to the 8,479 sites passing STEP 1; all of those have complete component scores. This is a screening utility, not a feasibility or interconnection assessment. The ranked [`STEP 3 Top 20`](outputs/validation/step3_top20.csv) and [`summary`](outputs/validation/step3_summary.json) retain components, plant name, match distance, and raw values for review. Exact duplicate name-and-coordinate rows are omitted from the display Top 20, but remain in the full Parquet. Top sites generally have strong line voltage, close line/substation, meaningful acreage, and name-corroborated EIA retired capacity; site-level due diligence remains necessary.

The manual Top 20 review finds a clear evidence drop after the first 13 rows: the remaining seven have strong grid/land screening attributes but no corroborated former-plant identity. They are explicitly recorded in `step3_summary.json` and should not be described as former power sites. The source data do not support filling all 20 ranks with equally strong former-plant evidence under this conservative identity rule.

## STEP 4: potential industrial heat sinks

`data/processed/industrial_facilities.parquet` has one row per FRS `REGISTRY_ID` with original NAICS and SIC strings, selected six-digit NAICS codes, and five sector flags. The selected sectors are 311 food manufacturing, 312 beverage, 322 paper, 325 chemical, and 331 primary metals. Multiple NAICS codes are split on commas and checked by their first three digits; a facility may belong to more than one sector, but it is counted once in total industrial counts. The source's NAD83 point coordinates are used as WGS84 screening approximations; this small datum difference is immaterial at 1/5/10 km radii, though exact parcel work needs surveyed coordinates. Rows without valid coordinates remain in the facility Parquet for lineage and are excluded from spatial measures.

`data/processed/candidate_sites_industrial.parquet` retains all 190,976 EPA sites and adds geodesic `industrial_sites_1km`, `industrial_sites_5km`, `industrial_sites_10km`; sector counts at 5 km; and exact nearest facility ID/name/NAICS/distance. [STEP 4 summary](outputs/validation/step4_summary.json) checks nested radii; the [seeded 20-site sample](outputs/validation/step4_random20.csv) exposes counts and the nearest facility for spot review. These are **potential industrial heat sinks** only. NAICS and distance do not show usable heat demand, heat grade, business interest, or physical pipeline feasibility.

## STEP 5: potential reclaimed-water opportunity

`data/processed/wastewater_facilities.parquet` contains 17,544 existing `Treatment Plant` records: 16,119 submitted CWNS IDs excluding `New` projects, plus 1,425 `confirmed_only` treatment plants from the confirmed wastewater population table. This reproduces the EPA dashboard's [17,544 reported treatment works](https://sdwis.epa.gov/ords/sfdw_pub/r/sfdw/cwns_pub/wastewater-dashboard), though 64 of these source records have non-public `OWNER_TYPE` (51 private and 13 federal). Facility identity is `CWNS_ID`; the source `FACILITY_ID` is also retained. All have reported residential population; 17,535 have current effluent treatment level; 16,114 have current total **design** flow in MGD. The 1,425 confirmed-only plants do not report design flow in this download. Only `Point` coordinates are used for spatial measures; 194 records with approximate/missing location remain in the facility layer but are excluded from distances. CWNS NAD83 points are used as WGS84 screening approximations.

`data/processed/candidate_sites_water.parquet` retains the full EPA site table and adds nearest treatment-plant ID/name/distance, 5/10 km plant counts, known design-flow sums, and counts of plants with reported design flow. Use `wwtp_count_*` to determine whether a plant lies in a radius: a zero flow sum can also mean that a nearby plant reported zero design flow. If nearby plants exist but none report flow, the sum is null with `water_flow_missing_reason`. Where only some report flow, the sum covers known plants only; `wwtp_flow_known_count_*` exposes coverage. The distance and counts use geodesic point calculations. [`STEP 5 random 20`](outputs/validation/step5_random20.csv), [`Top 20`](outputs/validation/step5_top20.csv), and [`summary`](outputs/validation/step5_summary.json) allow spot checks.

`water_reuse_component` is a **potential reclaimed-water opportunity** score: 60% proximity utility (distance in km 0–0.5→100, 2→90, 5→60, 10→0) plus 40% 10 km reported-design-flow utility (MGD 0→0, 1→15, 10→55, 100→100), linearly interpolated and capped. Missing design flow receives no flow credit but can retain proximity credit, with missingness recorded. This is not a water-availability estimate: actual flow, treatment suitability, water rights, infrastructure, and WWTP willingness require further investigation.

## STEP 6: separate industrial symbiosis axis

`data/processed/candidate_sites_symbiosis.parquet` retains all preceding source attributes and both distinct scores. `industrial_component` is 5 km potential-heat-sink density, with capped piecewise anchors count 0→0, 1→20, 5→45, 20→70, 50→90, 100→100. `heat_sink_proximity_component` uses nearest facility distance in km, 0–0.5→100, 1→90, 2→75, 5→45, 10→0. `wastewater_proximity_component` and `wastewater_availability_component` expose STEP 5's underlying distance and **reported design-flow** utilities; they combine as `water_reuse_component` = 60% proximity + 40% flow.

`symbiosis_score` = 25% industrial density + 25% heat-sink proximity + 50% water reuse. It contains no transmission, substation, land, or other inheritance inputs. The inheritance and symbiosis scores are kept as independent axes; no overall score is created. All utilities are capped at 0–100. The [standalone scatter plot](outputs/validation/inheritance_vs_symbiosis.html) shows all 8,479 passing EPA sites. The high-high quadrant uses explicit cutoffs `inheritance_score >= 60` and `symbiosis_score >= 75`, rather than relative ranks that would call weak inheritance scores “high.” Its [candidate table](outputs/validation/step6_upper_right.csv) and [summary](outputs/validation/step6_summary.json) preserve both scores and supporting fields. A quadrant hit is a screening lead, not proof of reusable infrastructure, heat offtake, or reclaimed-water availability.

## STEP 7: published candidate feature table

`data/processed/site_features.parquet` contains one row per **passing** STEP 1 candidate (8,479 rows), while `candidate_sites_symbiosis.parquet` continues to preserve all 190,976 EPA screening records. The published names `lat`, `lon`, `transmission_kv`, `transmission_distance`, `substation_distance`, `rail_distance`, and `road_distance` are explicit renames of the upstream fields with the same meaning; all other detailed metrics and components remain available. The required field list is in `src/processing/site_features.py`.

`missing_fields_count` checks 16 routinely expected identity/infrastructure/score fields, the three EIA power fields **only when** a former plant matched, and 5 km wastewater design flow **only when** at least one treatment plant lies within 5 km. An unmatched former plant is an explicit finding, not missing data. `data_quality_missing_fields` lists the affected fields. `data_quality_score` = max(0, 100 − 10 × missing count − proximity-confidence penalty − voltage-review penalty). The confidence penalties are very high 0, high 3, medium 8, low 15, unmatched 0; flagged unusual transmission voltage subtracts 10 and unusual substation voltage 5. This is a data-coverage/review-priority indicator, not a site feasibility score. The original `power_match_confidence` stays separate.

[STEP 7 summary](outputs/validation/step7_summary.json) records row/column counts, duplicate IDs, numeric ranges, and rankings. The [missingness table](outputs/validation/step7_missingness.csv) gives raw null counts by column; conditional inapplicability is instead handled by `missing_fields_count`. The three Top 20 lists are [inheritance](outputs/validation/step7_top20_inheritance.csv), [symbiosis](outputs/validation/step7_top20_symbiosis.csv), and [dual opportunity](outputs/validation/step7_top20_dual.csv). The dual list requires both scores at or above their candidate-set 75th percentiles and sorts by inheritance then symbiosis; it does not create a combined score.

## STEP 8: candidate explorer

Run `../.venv/bin/python -m scripts.build_site_explorer` from this folder to regenerate [the standalone explorer](outputs/infrastructure_inheritance_symbiosis.html) from `site_features.parquet`. It embeds all 8,479 candidates as JSON and draws one point per passing site. Seven controls filter the points and count in place; clicking a point opens the inspection panel. The former-power control requires `name_corrob` or `power_site_very_close` evidence (14 candidate rows), excluding proximity-only matches such as the Sunnyvale landfill/Yahoo! HQ pair; the published table still preserves all 472 raw nearby-EIA matches. The base map uses USGS USGSTopo tiles, with visible attribution, so tile loading and Leaflet still require an internet connection when opening the local HTML. No standard OpenStreetMap tiles are requested.

## STEP 9: evidence in the site panel

The right panel now presents the two independent scores with their component scores and source values. EIA former MW is explicitly historical retired-generator nameplate and does not establish available grid power or reuse rights. EPA line and substation distances, land, rail and road are source-reported screening values; the substation voltage's source unit is unresolved and displayed as raw only. FRS manufacturing counts and NAICS are potential heat-sink proxies. CWNS MGD is reported **design** flow, never actual available water. A nearby treatment plant with missing flow displays “Unknown”; a measured zero remains `0.00 MGD`. The data-quality count stays separate from both opportunity scores.

## STEP 10: coordinate-backed local ecosystems

Selecting a candidate draws its 5 km local inset around the candidate point, with source-coordinate FRS manufacturing facilities and CWNS treatment plants. Each plotted facility opens its name, type, WGS84 geodesic distance, source ID, and NAICS where available. `src/processing/local_ecosystem.py` builds the 84,263 site–facility pairs with exact `pyproj.Geod.inv` distances and a 5 km inclusive cutoff. [STEP 10 summary](outputs/validation/step10_summary.json) confirms 77,749 industry and 6,514 treatment-plant matches, with zero count mismatches versus the scored feature table. The 5 km outline is a display aid; pair inclusion and reported distances use WGS84 geodesics. EPA source data provide only nearest transmission/substation/rail distances, not those asset coordinates. The page therefore requests separate source-backed [HIFLD transmission geometry](https://services1.arcgis.com/Hp6G80Pky0om7QvQ/ArcGIS/rest/services/Electric_Power_Transmission_Lines/FeatureServer/0), [HIFLD substation points](https://services1.arcgis.com/7DRakJXKPEhwv0fM/ArcGIS/rest/services/Electric_Substations/FeatureServer/0), and [FRA/BTS 2026 rail segments](https://services.arcgis.com/xOi1kZaI0eWDREZv/arcgis/rest/services/NTAD_North_American_Rail_Network_Lines/FeatureServer/0) inside a 5 km buffer when a site is selected. These live layers have their own source lineage and may identify a different asset from the EPA nearest-distance field. A load status makes unavailable or truncated live layers visible. No guessed asset locations or network connections are drawn.

## STEP 11: public-record validation

[The validation report](outputs/validation/validation_report.md) audits 15 distinct candidates: five high-inheritance, five high-symbiosis, and five low-inheritance controls. [The selected-value CSV](outputs/validation/step11_selected_sites.csv) preserves the exact modeled fields; [automated checks](outputs/validation/step11_automated_checks.json) reconcile the published page, point bundle, null/zero counts and selected IDs. Official and other direct public records corroborate broad identity while revealing important siting-unit, activity-status, EIA proximity, FRS self-match and CWNS flow-definition risks. The report's linked records do not establish buildable land, grid power, heat offtake or reusable water.

## STEP 12: power and connectivity screening

This feature adds three raw indicators to the existing 8,479-site EPA screened cohort. It does not replace the candidate pool with small urban parcels and it does not certify suitability for a data center at or below 100 MW. The existing EPA filters were designed for large sites near transmission and remain a known limitation for this new use case.

| Indicator | Definition | Interpretation |
|---|---|---|
| `substation_distance_km` | Existing EPA distance to nearest substation, miles × 1.609344 | Smaller is geographically closer; it is not a capacity or interconnection measurement. |
| `peering_facility_distance_km` | WGS84 ellipsoidal geodesic distance to the nearest eligible US PeeringDB facility hosting at least one IXP | No distance cutoff is applied; for remote candidates this may be far away and represents the nearest listed facility only. |
| `peering_facility_network_count` | PeeringDB `net_count` from the exact facility selected for the distance indicator | Null means the directory count is unavailable; zero is a reported zero. The count is not bandwidth, traffic, latency, route diversity or a service guarantee. |

The current immutable source snapshot is `data/raw/peeringdb/20261003T233324Z`. The fetch window is recorded per page and in its `manifest.json`; seven pages contain 1,377 US source facility rows. Normalization retains 478 eligible IXP-hosting facilities and rejects 899 rows (876 without an IXP and 23 with invalid coordinates). PeeringDB pagination is not a transactional snapshot, so its retrieval interval is part of the lineage.

`data/processed/peering_facilities.parquet` is the normalized facility table. `data/processed/site_connectivity_features.parquet` has one row per existing candidate and preserves the nearest facility ID and the three raw metrics. `outputs/validation/power_connectivity_summary.json` and `power_connectivity_review.md` include source hashes and counts, link coverage, metric ranges, five smallest/largest values, unknown examples where present, a fixed-seed sample and limitations.

Rebuild these outputs explicitly from a ready local snapshot; the processing command does not fetch from the network:

```sh
../.venv/bin/python -m scripts.build_power_connectivity --snapshot data/raw/peeringdb/20261003T233324Z
../.venv/bin/python scripts/build_power_connectivity_report.py --snapshot data/raw/peeringdb/20261003T233324Z
../.venv/bin/python scripts.build_site_explorer.py \
  --connectivity-features data/processed/site_connectivity_features.parquet \
  --peering-facilities data/processed/peering_facilities.parquet \
  --peering-manifest data/raw/peeringdb/20261003T233324Z/manifest.json \
  --output outputs/power_connectivity_preview.html
```

The standalone preview adds a power-and-connectivity map with three independent filters and linked site/facility details, a log-scaled distance comparison where bubble area represents the facility's registered network count, and a sortable paged table. Map tiles require an internet connection; if Leaflet or the base map is unavailable, the metric filters, comparison chart and table remain usable. The legacy inheritance and symbiosis view remains available. These measurements indicate screening proximity and directory presence only; they do not establish available power, fiber routes, latency, buildable parcels, heat reuse, economics or 100 MW feasibility.
