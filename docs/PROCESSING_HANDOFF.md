# Processing handoff

All necessary baseline inputs are in `data/raw/`; start with
`python scripts/validate_data.py --geography` after installing requirements.
The partner can implement
`scripts/03_clean_merge.py` on a branch and submit a PR. Acquisition is complete;
cleaning and analysis are intentionally unfinished.

Observed source gaps: 187 counties have no crude or age-adjusted stroke estimate;
1,568 U.S. location rows have no site status, and five have no coordinates. See
`docs/SNAPSHOT_INVENTORY.md`. Any strict site-status cohort therefore has substantial
unknown coverage; report this before interpreting zero-site counties.

All 120 Kentucky counties and all 67 Pennsylvania counties have missing stroke
estimates in this snapshot. Exclude missing estimates from median calculation and
keep desert flags missing for those counties. Show these states as “no estimate”
on prevalence maps, not as low-burden areas.

## Load the inputs

Run this from the repo root in the configured Python environment:

```python
import json
from pathlib import Path
import pandas as pd
import geopandas as gpd

root = Path.cwd()
places = pd.read_csv(root / "data/raw/places_county_2025.csv",
                     dtype={"countyfips": "string"})
studies = json.loads((root / "data/raw/clinicaltrials_stroke.json").read_text())["studies"]
counties = gpd.read_file(root / "data/raw/cb_2023_us_county_500k.zip")
```

Production scripts should resolve paths from `__file__`, as the download scripts
do, so they also work outside the repo root. The boundary file has territories
outside the intended study scope; restrict analysis to eligible PLACES counties.

## Processing sequence

1. Keep PLACES FIPS as five-character strings, state/county names, population,
   crude and age-adjusted stroke prevalence, and their intervals. Audit missing
   counties and values. Preserve missingness rather than treating it as zero.
2. Flatten each study's locations while retaining study ID/title/conditions,
   overall status, phase, and update date. Keep U.S. locations, then enforce the
   50-states-plus-DC scope and report excluded territories and unknown states.
3. Review the condition search cohort. Document any clinical-topic exclusions
   using explicit criteria and NCT IDs, not arbitrary title substring filters.
4. Define trial/site duplicates using study ID and normalized facility/address
   fields. Audit ambiguous/blank facility names. Coordinate-only deduplication
   is inappropriate because multiple sites may share city-level coordinates.
5. Create points from longitude/latitude and transform county polygons to the
   same CRS. Join points to county polygons. Keep sites with absent coordinates,
   multiple polygon matches, or no match in a review table. Check source state
   against assigned county state. Do not silently use the nearest county.
6. Aggregate qualifying trial/site pairs to county. Separately compute unique
   facilities if feasible. A facility hosting five trials is five trial/site
   pairs but one facility; labels must make this distinction clear.
7. Left join counts onto PLACES so counties without matched sites remain present.
   Confirm one row per county, no join expansion, and reconciliation of site
   totals. Zero means no qualifying **observed assigned** sites, not guaranteed
   lack of access. Quantify the effect of unassigned sites on conclusions.
8. Generate features, save the processed CSVs and quality report, update the
   README with the exact processing command, and open a reviewed PR.

## Suggested definitions to review before implementation

- **Recruiting access:** overall study status `RECRUITING` and site status
  `RECRUITING`. Do not infer recruiting from a missing site status.
- **Invitation enrollment:** report `ENROLLING_BY_INVITATION` separately; it is
  not general open recruitment.
- **Broader active infrastructure:** within the acquired study cohort, count sites
  whose site status is `RECRUITING`, `ENROLLING_BY_INVITATION`, or
  `ACTIVE_NOT_RECRUITING`. Exclude completed/withdrawn/etc. sites and report
  missing status as unknown. This is an infrastructure measure, not enrollment.
- **Primary burden:** crude stroke prevalence; compare age-adjusted prevalence as
  a sensitivity analysis since county age structure can influence crude rates.
- **Rate:** `100000 * qualifying_trial_site_count / total_population`. This is
  sites per 100,000 all-age residents. An adult-population version may better
  align with PLACES; if used, name and label that denominator explicitly.
- **Potential trial desert:** prevalence strictly greater than the unweighted
  median across eligible counties with nonmissing prevalence, and zero qualifying
  observed sites. Document whether the recruiting or broader active count is used;
  retain both versions as a sensitivity comparison.
- Avoid prevalence divided by a zero site rate. Do not convert infinity or missing
  prevalence to an arbitrary mismatch score. The binary feature is sufficient.

These are proposed analysis choices for the partner to review, not completed
methods. Compare definitions before making public claims.

## Processing PR acceptance checks

- Source hashes still pass, and no input files were overwritten by cleaning.
- Five-digit FIPS and exactly one row per county in the final table.
- All PLACES counties accounted for; excluded/missing areas listed explicitly.
- Site counts reconcile after country/status/duplicate/assignment exclusions.
- Unknown site status and missing coordinates reported rather than guessed.
- County CRS, source coordinate precision, border cases, and Connecticut county
  equivalents considered. Do not combine incompatible county vintages.
- Counts are nonnegative; denominators positive or reported missing; no infinite
  engineered features. Missing prevalence does not become a desert flag of false.
- Every exported table is documented and can be regenerated by a script.
- Quality report lists unresolved limitations before visualizations are published.
