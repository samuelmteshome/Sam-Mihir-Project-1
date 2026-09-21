# Stroke mortality and distance to trial sites

This extension adds death counts and a population-based access measure to the
existing prevalence analysis. It is descriptive and uses the existing cleaned
ClinicalTrials.gov cohort; it does not identify patient addresses or imply that
an active trial site accepts every stroke patient.

## Reproduce offline

Install `requirements.txt`, then run:

```bash
python scripts/03_clean_merge.py
python scripts/05_get_access_outcomes.py   # verifies committed snapshots; no network by default
python scripts/06_analyze_access_outcomes.py
python scripts/validate_data.py
python -m unittest discover -s tests -v
```

Use `--refresh` on script 05 only to intentionally replace the new raw snapshots.
It records source URLs, retrieval time, counts, field selection, and SHA-256
checksums. The full HRSA archive is downloaded transiently; only nine relevant
public NCHS/Census/USDA fields and the documentation archive are committed.
The original partner outputs are read, never overwritten by script 06.

## Sources

| Source | Period / measure | Use |
|---|---|---|
| [Census population centers](https://www.census.gov/geographies/reference-files/time-series/geo/centers-population.html), [national tract file](https://www2.census.gov/geo/docs/reference/cenpop2020/tract/CenPop2020_Mean_TR.txt) | 2020 tract population and population-weighted mean latitude/longitude | Distance origins and population weights |
| [Census 2020 county boundaries](https://www2.census.gov/geo/tiger/GENZ2020/shp/cb_2020_us_county_500k.zip) | 1:500,000 cartographic boundaries | Reassign existing trial coordinates to the historical county definitions |
| [HRSA AHRF downloads](https://data.hrsa.gov/data/download?data=AHRF), 2024–2025 county release | NCHS cerebrovascular deaths, ICD-10 I60–I69; all ages; annual average for 2021–2023 and 2020–2022 | Actual county mortality counts, not age-adjusted rates |
| Same HRSA release | USDA 2023 Rural-Urban Continuum Code and Census 2020 rural population | County metropolitan context; source rural-population field retained for further analysis |
| Existing ClinicalTrials.gov snapshot | Retrieved September 20, 2026 | Existing cleaned interventional stroke-related trial locations |

The HRSA technical documentation maps `cerbrvsc_dis_deth_3yr_23` to the NCHS
Mortality File for 2021–2023. The archived User Guide's section “2020–2022 and
2021–2023 Mortality Average Data” defines county residence, exclusion of non-US
residents, and the three-year sum divided by three. Its Table 14 specifies
I60–I69. AHRF reports these averages as whole numbers. Do not multiply by three
and describe the result as an exact three-year death total.

AHRF suppresses low county counts under NCHS disclosure rules. Blank values
also can mean unavailable data. Preserve blanks and use `mortality_published`;
never fill mortality with zero or reconstruct individual suppressed values.
The publisher's download page lists no usage limitations.

## Definitions and denominators

**Population distance:** 84,414 tracts containing 331,449,281 residents in the
50 states and DC. Each tract's entire population is assigned its population-
weighted mean center. Compute Haversine distance to the nearest eligible
registry coordinate, allowing sites across county and state borders. Weight
the empirical distance distribution by tract population. “Beyond 50 miles”
uses strictly greater than 50, and percentiles use the inverse weighted CDF.
Zero-population tracts do not affect the results. Territories are excluded.
These are 2020 residents of all ages, not current population estimates,
citizenship counts, stroke patients, or household-level distances.

This method approximates access within large tracts. Registry points may be
city centers and several facilities can share one point. Identical coordinates
are deduplicated for the nearest-distance calculation, not labeled unique
hospitals. Straight-line distance is not driving distance, ambulance response
time, travel feasibility, or access to acute stroke treatment.

**Site cohorts:** `active` uses the partner's known-active site flag (recruiting,
enrolling by invitation, or active/not recruiting). `recruiting` also requires
overall study and site status to be recruiting. An additional sensitivity
scenario includes active sites plus sites with unknown status; this is not
confirmed availability. All cohorts use the partner's retained, state-consistent
coordinates. Five upstream review rows lacking coordinates are not imputed.
The pipeline fails if a retained point cannot be uniquely assigned to a matching
state in the 2020 county boundaries.

**Mortality share:** sum published annual-average deaths in counties with zero
qualifying trial/site pairs, divided by the sum across all counties with
published counts. The current snapshot has 1,995 published county counts and
1,148 suppressed/missing counties. Excluded counties disproportionately include
small populations; the observed share is not a national estimate or a complete
rural mortality share. It does not measure individual deceased people's distance
from a trial site. Deaths predate the registry snapshot, so “no site” describes
2026 records, not a verified absence during 2021–2023.

**Metro/nonmetro:** USDA RUCC 1–3 = metro, 4–9 = nonmetro. This classifies counties;
it does not mean all residents of a nonmetro county live in rural census areas.
Historical Connecticut counties lack 2023 RUCC codes and remain `unavailable`.

## Geography compatibility

The original analysis uses 2023 boundaries and Connecticut's nine planning
regions. Mortality uses its eight historical counties. This extension uses
2020 counties for both site presence and death counts, preserving Connecticut
in the primary mortality analysis. This explains why the active-site county
count differs slightly from the partner's 2023-based count.

`county_analysis_with_mortality.csv` offers a convenient left join to the
partner's existing county table. Its nine Connecticut planning-region rows
have `mortality_geography_match=False`, with new mortality and distance fields
missing. Do not replace those missing values with zero or distribute county
counts across planning regions without an appropriate crosswalk. The full
historical-county analysis lives in `county_mortality_access.csv`. Loving County,
Texas is present in that file and the population calculation even though it is
absent from the original PLACES table.

## Output field guide

| File / fields | Meaning |
|---|---|
| `tract_trial_distance.csv`: `tractfips_2020`, `countyfips_2020`, `POPULATION`, `LATITUDE`, `LONGITUDE` | Original Census origin and population; FIPS must be read as text |
| `nearest_active_miles`, `nearest_recruiting_miles`, `nearest_active_plus_unknown_sensitivity_miles` | Great-circle miles from tract population center to closest qualifying registry point |
| `county_mortality_access.csv`: `stroke_deaths_annual_avg_2021_2023`, `stroke_deaths_annual_avg_2020_2022` | Published annual-average counts, all ages; blank remains missing |
| `mortality_published` | Primary 2021–2023 count is available |
| `trial_site_pairs_*` | Trial/facility pairs assigned to the historical county; not distinct hospitals |
| `population_mean_*_miles` | County average of tract nearest-site distances weighted by resident population; not deceased-person distance |
| `rural_urban_contnm_23`, `metro_status_2023` | Source RUCC and derived metro/nonmetro/unavailable label |
| `cens_popn_20`, `cens_rural_popn_20` | AHRF's source population fields, retained without imputation |
| `county_analysis_with_mortality.csv` | Existing PLACES analysis plus compatible new features and geography-match flag |
| `reports/access_outcomes_summary.json` | Full-precision metrics, input hashes, cohort sizes, suppression and geography coverage |
| `reports/access_outcomes.md` | Slide wording and sensitivity results |
| `figures/population_trial_distance.png`, `figures/stroke_mortality_trial_access.png` | Exportable figures with scope and denominator notes |

The older mortality window overlaps the primary window. It is included for
future comparison, not an independent before/after evaluation. None of these
outputs measures stroke-attributable disability, treatment benefit, or a causal
effect of trial geography on death. Use this feature to discuss geographic
representation and access, not to infer that tPA should be given later in rural
communities.
