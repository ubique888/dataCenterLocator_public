# Six-page story — a metro inference node, not a generic hyperscale campus

**Audience:** hackathon judges. **Scope:** `infrastructure-inheritance-symbiosis` only. **Proposed system:** metropolitan inference nodes at or below 100 MW, connected to lower-cost regional facilities for delay-tolerant work. **Current location result:** Astoria, Queens is a screening lead and demo case, not a verified network-first winner or approved parcel. **As of:** 2026-10-03.

**Central claim to test:** Put latency-sensitive inference close to users and network exchanges. Route work that tolerates delay to cheaper regional facilities. Reuse existing infrastructure and waste heat where measured conditions support it. This is a workload-placement and network-design question as much as a land-selection question.

## Page 1 — Counterintuitive question: why put inference in a city?

**Headline:** What if the best place for an AI data center is near the request, rather than near the cheapest land?

**Why it matters:** Interactive inference is judged by end-to-end response time: network round trip, queuing, first-token time and generation speed. Geography can matter when users or data are concentrated in a metro. AWS describes its Local Zones as placing latency-sensitive application components near users; NVIDIA's inference architecture treats routing, cache locality, latency and throughput as distinct operating concerns. These support the service pattern, not any particular site's suitability. [AWS Local Zones](https://aws.amazon.com/about-aws/global-infrastructure/localzones/faqs/) · [NVIDIA inference reference architecture](https://docs.nvidia.com/ncx/ncp-inference-ra/).

**System visual:** User demand → metro inference node with current accelerators and cached models → regional, lower-cost facility for delay-tolerant or throughput-oriented work. Route by service objective, data locality, model availability and total cost. “Simple” and “complex” are insufficient labels: a small request can have a strict latency target; a heavy job can be asynchronous.

**Beyond this factor:** The question becomes which *portfolio of nodes and routing policy* beats a regional-only baseline on latency, cost and environmental impact. The project has not implemented that comparison.

## Page 2 — Density = cost + opportunity

**Headline:** Urban density puts users, networks and possible heat customers nearby, while tightening land, power and community constraints.

| Factor | Why it matters | What the project can and cannot establish |
|---|---|---|
| User and network proximity | It can reduce request travel time and expand routing options. | PeeringDB gives distance to a listed IXP-hosting facility and its registered network count. It does not measure p95/p99 user latency, packet loss, carrier diversity, fiber route, bandwidth or contract terms. |
| Grid and industrial land | Existing infrastructure may reduce new works and embodied materials. | EPA line/substation distance and EIA retired-generator proximity are screens. Utility-deliverable MW, upgrades, current land use and reuse rights are unknown. |
| Heat customer | A nearby, continuous demand can make waste heat useful. | FRS industry type and distance do not measure heat demand, temperature, pipe route or a commercial agreement. [DOE heat-reuse guide](https://www.energy.gov/sites/default/files/2024-07/best-practice-guide-data-center-design.pdf). |
| Urban costs and effects | Land, power, permits, cooling, noise and community support can decide feasibility. | The current model does not price or verify them. |

**Implemented evidence:** The explorer screens **190,976** EPA RE-Powering site records to **8,479** using reported ≥50 acres, ≤3 miles to transmission, ≥115 kV and ≤5 miles to a substation. Of those, **5,185** have a selected FRS manufacturing point within 5 km and **4,409** have a CWNS treatment-plant point within 5 km. The inherited ≥50-acre filter excludes many compact urban sites this new thesis would need to evaluate. [`README_DATA.md`](../README_DATA.md) · [`validation_report.md`](../outputs/validation/validation_report.md).

**Beyond these factors:** Density creates value only if the node actually serves nearby traffic, can receive power and has real resource users. A proximity score alone cannot show that.

## Page 3 — Infrastructure symbiosis and the GPU life cycle

**Headline:** Design the node as part of an urban system, then account for hardware after its first use.

**What is implemented:** The project links EPA candidates to EIA retired-generator points, selected EPA FRS manufacturing facilities, EPA CWNS treatment plants and eligible PeeringDB IXP-hosting facilities. A site explorer preserves source IDs and raw distances; a 5 km inset shows source-coordinate industrial and treatment-plant points. A separate preview filters by substation distance, PeeringDB facility distance and that facility's registered network count. Live HIFLD transmission/substation and FRA rail geometry provide context, not confirmed connections. [`README_DATA.md`](../README_DATA.md) · [`power_connectivity_review.md`](../outputs/validation/power_connectivity_review.md).

**Why it matters:** Reusing industrial context may avoid some new works. Real network routes determine whether the metro node meets its latency goal. Heat reuse can displace heat produced elsewhere, but DOE notes that it depends on a nearby consumer, useful temperature and operating arrangements; the data center still needs heat rejection when no customer can take it. [DOE design guide](https://www.energy.gov/sites/default/files/2024-07/best-practice-guide-data-center-design.pdf).

**Hardware implication:** A metro node may use newer accelerators for latency-sensitive inference and later redeploy, refurbish or resell usable equipment. Resale is a *possible residual value*, not a guaranteed financial or environmental gain. Assess purchase cost, performance per watt, operating life, refurbishment, secure data erasure and end-of-life handling together. EPA recognizes reuse and refurbishment as ways to extend electronics' lives. [EPA electronics stewardship](https://www.epa.gov/electronics-batteries-management/electronics-basic-information-research-and-initiatives).

**Beyond these factors:** Heat reuse and hardware circularity affect the business model and life-cycle footprint. Neither rescues a site without a viable power connection or a workload that benefits from the location.

## Page 4 — Decision engine: what exists and what the new thesis needs

**Headline:** Today's tool finds infrastructure-symbiosis leads; network-first inference requires another decision layer.

**Implemented today:** Stage 1 applies the four EPA thresholds on Page 2. Stage 2 keeps independent 0–100 axes: **infrastructure inheritance** = 30% power legacy + 25% transmission + 20% substation distance + 15% land + 10% transport, with an identity-evidence gate; **industrial symbiosis** = 25% industry density + 25% nearest potential heat-user proximity + 50% treatment-plant proximity/reported design-flow opportunity. There is no blended score. The **8,479 × 71** feature table, quality indicator, Top 20 exports, map filters and local ecosystem view are implemented. Connectivity is a separate raw-indicator preview and is not part of either score. [`README_DATA.md`](../README_DATA.md) · [`step7_summary.json`](../outputs/validation/step7_summary.json).

**Decision sequence required by the new thesis:**

1. **Hard gates:** real parcel/building and permitted use; utility-deliverable MW and timeline; cooling/redundancy; real fiber/carrier routes; security and resilience.
2. **Measured service fit:** demand-weighted p95/p99 latency, throughput, availability, model/cache placement, inter-site transfer and fallback.
3. **Portfolio comparison:** metro plus regional routing versus regional-only service, measured in cost per useful inference, carbon, water, embodied materials, delivered heat and community effects.
4. **Robustness and future:** demand growth, hardware efficiency, energy price/grid mix, network failures, seasonal heat demand and climate risk.

**Boundary:** User-demand maps, measured end-to-end latency, utility MW availability, capex/opex, workload routing, sensitivity sampling, future scenarios and quantified sustainability impact are **not implemented** in this subproject. PeeringDB distance and network count are exploratory clues, not a high-speed connection score. NVIDIA also calls for workload-specific latency, throughput and cache measurement. [NVIDIA inference reference architecture](https://docs.nvidia.com/ncx/ncp-inference-ra/).

**Beyond the factors:** The eventual output should be an explainable *deployment and routing plan* rather than one static site ranking.

## Page 5 — Below 100 MW still requires serious power planning

**Headline:** Scale changes the geography and engineering gate; it does not remove the grid requirement.

**Why it matters:** “≤100 MW” spans very different facilities. A continuous **100 MW facility load** implies **876 GWh/year** by arithmetic; 50 MW implies **438 GWh/year**. These are illustrations, not forecasts of actual utilization. A compact GPU facility can have high rack, electrical and cooling density despite modest acreage. IEA emphasizes the concentrated local impact of data-center demand and rising accelerator power density. [IEA Energy and AI](https://www.iea.org/reports/energy-and-ai/energy-demand-from-ai) · [IEA executive summary](https://www.iea.org/reports/energy-and-ai/executive-summary%C2%A0).

**Precise hypothesis:** A smaller, phased metro node *may* use existing utility and colocation infrastructure and avoid a dedicated generation complex. That depends on the actual load, utility study, redundancy requirements and upgrade schedule. Do not claim 100 MW needs no major power allocation or electrical works.

**Actual candidate contrast:** Astoria's EPA record reports **215 acres**, **138 kV** nearest line and zero reported miles to line/substation. The Salem-area New England Power Company record reports **64 acres**, **115 kV** and zero reported miles to line/substation. Their matched EIA historical retired-generator nameplate values are **666.1 MW** and **805.1 MW**; neither is available capacity. Their nearest eligible PeeringDB facility distances are **9.55 km** and **23.41 km**; neither predicts user latency. [`step6_upper_right.csv`](../outputs/validation/step6_upper_right.csv) · [`site_features.parquet`](../data/processed/site_features.parquet) · [`site_connectivity_features.parquet`](../data/processed/site_connectivity_features.parquet).

**Beyond the factor:** Evaluate explicit load and rack-density scenarios rather than treating 1 MW and 100 MW as the same siting class. Reopen the candidate universe to smaller metro buildings and parcels.

## Page 6 — Demo result and wider implications

**Headline:** Astoria is an evidence-rich lead; the winning *strategy* is a measured metro-to-regional inference network.

**Current demo:** Set inheritance ≥60 and symbiosis ≥75: only **two** of the 8,479 screened sites remain. Astoria, Queens (EPA ID **40157**) scores **78.46 / 93.21**. The EIA Astoria Gas Turbines point is **0.252 km** away with name corroboration; **37** selected manufacturing points and **3** treatment-plant points are within 5 km. Its nearest eligible PeeringDB IXP-hosting facility is **9.55 km** away with **1** registered network in this snapshot. Salem is the other high-high lead at **61.19 / 79.99**. These do not prove that Astoria has the fastest network, usable power or best economics. [`step6_summary.json`](../outputs/validation/step6_summary.json) · [`step6_upper_right.csv`](../outputs/validation/step6_upper_right.csv) · [`power_connectivity_summary.json`](../outputs/validation/power_connectivity_summary.json).

**Demo path:** Show the two-axis explorer and Astoria's 5 km ecosystem, then the separate power/connectivity preview. State the decisive next test: measure user-to-building latency through real carriers, obtain utility MW/timeline evidence, and benchmark metro-plus-regional routing against a regional-only deployment.

**Recommendation:** Advance **Astoria/Queens as the first due-diligence region**, keep Salem as a comparison, and reopen the pool to compact metro sites before naming a network-first winner. Newtown Creek shows why: its high symbiosis score comes from an EPA point representing a waterbody cleanup area, not a buildable 166-acre parcel. [`validation_report.md`](../outputs/validation/validation_report.md).

**Implications beyond site factors:**

- **Operations:** routing, cache/model placement and fallback become part of siting. Compare a *completed inference request across the network*, including regional offload.
- **Economics:** latency value must exceed urban land, power, network and cooling premiums; resale is uncertain residual value.
- **Sustainability:** measure net electricity, carbon, water and materials against a baseline. Efficiency per request can improve while total demand still grows.
- **Community/resilience:** multiple nodes can diversify service, while each still needs utility, cooling, noise, disaster and neighborhood review.
- **20–30 years:** phase nodes with measured demand, refresh and responsibly reuse hardware, and update routing and energy arrangements as models, grids, users and climate risks change.

**Close:** The project proves a traceable *screening workflow*. The next proof is workload-specific latency and utility capacity, followed by life-cycle sustainability—not another proximity-only score.

## Source of truth and demo artifacts

- [`README_DATA.md`](../README_DATA.md) — data lineage, scoring and limitations.
- [`validation_report.md`](../outputs/validation/validation_report.md) — 15 public-record checks and observed false positives.
- [`power_connectivity_review.md`](../outputs/validation/power_connectivity_review.md) — PeeringDB coverage and proxy limits.
- [`infrastructure_inheritance_symbiosis.html`](../outputs/infrastructure_inheritance_symbiosis.html) and [`power_connectivity_preview.html`](../outputs/power_connectivity_preview.html) — existing demo artifacts.
