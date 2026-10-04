# Speaker notes

Target delivery: about five minutes including transitions. Pace: approximately 125–140 words per minute. These notes are embedded in the PPTX as well.

## Slide 1 — 35 seconds

The obvious answer for a data center is cheap land far from the city. Our project asks whether that changes for interactive AI inference. A request has to reach the model and return to the user, so the right location can depend on the network and the people it serves. We are testing an urban industrial site as a compact inference node, with slower work sent to a lower-cost regional facility. This is a siting hypothesis, not a measured latency result.

Source: `../docs/six_page_story.md`, Page 1.

## Slide 2 — 40 seconds

Density cuts both ways. Urban land is contested, grid connections can be difficult, and permits and community impacts matter. The same area may also contain users, network facilities, skilled workers, industrial land and customers for waste heat. Our locator measures some physical proximity, especially grid, selected industry and treatment plants. It does not price land or prove a workforce, a heat contract or a fiber route. We therefore treat density as a reason to investigate specific sites, not as an automatic sustainability advantage.

Source: `../docs/six_page_story.md`, Page 2; `../README_DATA.md`.

## Slide 3 — 45 seconds

This diagram is the project thesis. A prospective inference site sits inside six surrounding systems. Grid assets may support an interconnection. Carrier routes and nearby users make a metro service plausible. Industrial neighbors might use low-grade heat. A treatment plant might support a reclaimed-water cooling design. Reusing an industrial footprint may reduce some new land or material needs. The current project maps candidate points and nearby source records. It does not prove any connection, available megawatts, usable water, heat demand or parcel rights. Each link is a due-diligence question.

Source: `../README_DATA.md`, Steps 1–12; `../outputs/validation/validation_report.md`.

## Slide 4 — 45 seconds

Here is what we have actually built. We start with 190,976 EPA RE-Powering records. Reported acreage and grid-distance thresholds yield 8,479 screened candidates. Each receives two separate opportunity scores. Infrastructure inheritance uses former power, transmission, substation, land and transport evidence. Industrial symbiosis uses selected manufacturing proximity and treatment-plant opportunity. The explorer exposes source values and a five-kilometer local ecosystem. Connectivity indicators sit in a separate preview, not in either score. The original 50-acre threshold also means compact urban parcels are missing from this candidate pool.

Source: `../outputs/validation/step1_summary.json`; `../outputs/validation/step7_summary.json`; `../README_DATA.md`.

## Slide 5 — 40 seconds

The separate axes make tradeoffs visible. Astoria and the Salem-area New England Power Company record both clear the current high-high thresholds. Indian Point has stronger inheritance but less surrounding symbiosis. Davis Street shows the opposite pattern and has an active facility-use question. Scores narrow the field. They do not settle parcel availability or data-center feasibility. The separate connectivity view tells us which facilities to investigate further, but its distance to a listed IXP-hosting building cannot establish user latency or a fiber contract.

Source: `../outputs/validation/step6_upper_right.csv`; `../outputs/validation/step11_selected_sites.csv`; `../outputs/validation/power_connectivity_review.md`.

## Slide 6 — 45 seconds

Our first diligence lead is Astoria in Queens, EPA candidate 40157. It scores 78.46 for infrastructure inheritance and 93.21 for industrial symbiosis. An independent recount found 37 distinct FRS facility IDs within five kilometers, across 34 coordinate groups. The selected manufacturing categories are food 3, beverage 4, paper 6, chemicals 15, and primary metals 9. These records suggest heat-reuse opportunities to investigate; they are not confirmed heat customers. Current operations, heat quantity and temperature, pipe feasibility, and willingness to partner have not been checked. Nor have parcel rights, utility capacity, or network performance. Astoria is a diligence lead, not a construction-ready site.

Source: `../outputs/validation/step6_upper_right.csv`; `../data/processed/site_features.parquet`; `../outputs/validation/validation_report.md`; user-provided independent Astoria recount of FRS IDs, coordinates and categories.

## Slide 7 — 45 seconds

The long-term case rests on more than today's score. Residents and firms generally do not relocate across regions all at once, so a metro can remain a useful catchment for latency-sensitive services. That is a planning premise, not a thirty-year demand forecast; we would recheck migration and workloads at every phase. Suitable suburban parcels near fiber and grid are also more limited than remote acreage, making site options valuable. Utility, carrier and heat links may last longer than one GPU generation. We can refresh hardware and shift eligible work to regional facilities as needs change. First, though, we still need parcel, utility, carrier and heat-use diligence. The timeline remains conditional.

Source: `../docs/six_page_story.md`, Pages 4–6.
