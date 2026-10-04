# Power & connectivity coverage review

- Candidate cohort: Existing EPA screened candidates · ≥50-acre source cohort
- EPA source: EPA RE-Powering America’s Land Initiative, 2022 release updated 2023
- PeeringDB snapshot: `20261003T233324Z` (ready)
- Retrieval window: 2026-10-03T23:33:24.298648Z to 2026-10-03T23:33:25.668704Z
- Snapshot SHA-256: `35dc046731d6e107cecb620c90e9974e3ba64730b98342c9df270d6305b537d7`

## PeeringDB coverage

| Item | Count / value |
|---|---:|
| US source facility rows | 1,377 |
| Eligible IXP-hosting facilities | 478 |
| Rejected source rows | 899 |
| Eligible facilities with unknown network count | 0 |
| Snapshot pages, including terminal empty page | 7 |

Rejected rows by reason:

- `invalid_coordinates`: 23
- `no_ixp`: 876

Page file hashes are listed in `power_connectivity_summary.json`; the combined hash covers the ordered file paths and hashes. The API traversal is not a transactional snapshot, so the retrieval interval is part of the source record.

## Candidate linkage

- Base sites and metric rows: 8,479 / 8,479; exact ID match: True.
- Connectivity states: `{"matched": 8479}`.
- Nearest-facility relations: 8,479 across 283 unique facilities; relation and same-facility network-count checks passed.

## Metric coverage and extremes

| Metric | Unit | Known | Unknown | Zero | Minimum | Maximum |
|---|---|---:|---:|---:|---:|---:|
| Nearest substation distance | km | 8,479 | 0 | 896 | 0.0000 km | 8.0439 km |
| Nearest listed IXP facility distance | km | 8,479 | 0 | 0 | 0.1933 km | 1,710.3882 km |
| Networks at that nearest facility | registered networks | 8,479 | 0 | 21 | 0 | 334 |

The registered network count describes PeeringDB directory entries at the selected facility; it does not indicate bandwidth, traffic capacity, latency, or a service commitment.

### Nearest substation distance

Existing EPA nearest-substation distance in miles × 1.609344. Direction: smaller is geographically closer.

Five smallest known values:
- site `126`, facility `6085`, value `0.0000 km`
- site `201`, facility `3441`, value `0.0000 km`
- site `219`, facility `14600`, value `0.0000 km`
- site `227`, facility `16052`, value `0.0000 km`
- site `315`, facility `16052`, value `0.0000 km`
Five largest known values:
- site `145432`, facility `8032`, value `8.0439 km`
- site `18762`, facility `6670`, value `8.0407 km`
- site `160036`, facility `1423`, value `8.0345 km`
- site `171455`, facility `7740`, value `8.0337 km`
- site `158165`, facility `1423`, value `8.0228 km`
Unknown-value examples:
- No unknown values in this build.

### Nearest listed IXP facility distance

WGS84 ellipsoidal geodesic to the nearest eligible US PeeringDB facility hosting an IXP. Direction: smaller is geographically closer.

Five smallest known values:
- site `38104`, facility `468`, value `0.1933 km`
- site `140226`, facility `468`, value `0.1997 km`
- site `202590`, facility `7872`, value `0.2380 km`
- site `138135`, facility `7872`, value `0.2458 km`
- site `154313`, facility `585`, value `0.2876 km`
Five largest known values:
- site `43735`, facility `3441`, value `1,710.3882 km`
- site `210`, facility `3441`, value `1,708.5563 km`
- site `43734`, facility `3441`, value `1,708.1191 km`
- site `40903`, facility `3441`, value `1,689.2879 km`
- site `201`, facility `3441`, value `1,688.1457 km`
Unknown-value examples:
- No unknown values in this build.

### Networks at that nearest facility

PeeringDB net_count from the same facility selected for the nearest-facility distance. Direction: larger is more networks listed in PeeringDB.

Five smallest known values:
- site `2679`, facility `766`, value `0`
- site `5095`, facility `766`, value `0`
- site `15049`, facility `766`, value `0`
- site `16208`, facility `766`, value `0`
- site `24208`, facility `766`, value `0`
Five largest known values:
- site `1087`, facility `7`, value `334`
- site `1248`, facility `7`, value `334`
- site `1255`, facility `7`, value `334`
- site `25007`, facility `7`, value `334`
- site `34826`, facility `7`, value `334`
Unknown-value examples:
- No unknown values in this build.

## Fixed random sample

Seed: `20261003`. Values are raw Parquet values; the sample selection method is recorded in the JSON.

| site_id | facility_id | Substation km | Nearest facility km | Networks at same facility |
|---:|---:|---:|---:|---:|
| 42171 | 2621 | 0.1852 km | 83.0385 km | 8 |
| 159156 | 1423 | 5.2897 km | 52.9331 km | 7 |
| 160343 | 1423 | 4.8133 km | 89.5246 km | 7 |
| 171671 | 710 | 4.0313 km | 143.7186 km | 10 |
| 150726 | 3669 | 0.5074 km | 61.1453 km | 4 |

## Scope limits

- The 8,479 rows are the existing EPA screened cohort; they are not a national inventory of small urban or industrial parcels.
- PeeringDB facilities are US records with at least one listed IXP; this is not a complete fiber, carrier PoP, or data-center inventory.
- Geographic proximity does not establish available power, interconnection capacity, network latency, bandwidth, route diversity, or service rights.
- No combined score or 100 MW feasibility certification is derived from these three indicators.

## Implementation QA

- Data build: `scripts.build_power_connectivity --snapshot data/raw/peeringdb/20261003T233324Z` completed with 8,479/8,479 sites matched, 8,479 valid nearest-facility relations and 283 referenced facilities. The selected facility's `net_count` matched the same facility ID for every site. The generated HTML also embeds the existing 84,263 local ecosystem matches.
- Source dates and scope: the page shows the EPA RE-Powering 2022 release updated in 2023, PeeringDB retrieval date 2026-10-03, snapshot ID `20261003T233324Z`, and the existing ≥50-acre screened cohort.
- Filter/view consistency: in the browser, setting maximum substation distance to 0.1 km yielded 1,092 matches; the shared comparison/table state retained that filtered count, and the table showed page 1 of 22 with 50 rows. Sorting and paging are covered by UI unit tests.
- Missing and zero values: the production snapshot has no unknown values for these three metrics; it has 896 zero substation distances and 21 zero registered network counts. UI tests separately cover null values, zero markers, and unbounded filters retaining unknowns.
- Legacy view: switching to `Inheritance & symbiosis` retained its original filters, map and all 8,479 candidates.
- Desktop and narrow screen: the map, fixed-bin legend, filters and source note rendered in a 1280 × 720 desktop browser. The map, comparison chart and paged table were inspected at 390 × 844; filter labels and units remain readable and the table scrolls horizontally.
- Base-map failure: an ephemeral validation copy with Leaflet CSS/JavaScript removed displayed the map-unavailable message while filters still showed 8,479 candidates, the comparison canvas rendered and the table remained available with 50 rows per page. Selecting a table row marked it `aria-selected` and opened details without Leaflet; closing details cleared selection. The delivered preview uses USGS tiles with visible attribution.
- Data safety: missing eligibility fields abort import and do not publish a ready snapshot; a missing `net_count` remains a null/unknown. Template token collision tests retain user source text and JSON parsing.
- Independent review: no Critical or Important findings remain. The reviewer notes the nontransactional nature of offset pagination, already disclosed above.
- Automated tests: the Task 6 focused suite passed (36 tests), and the complete feature-project suite passed (70 tests).
