# Clinical Trial Deserts

**Are U.S. stroke trials located where stroke burden is highest?**

Sam and Mihir's AIPI 510 Project 1 compares county-level adult stroke prevalence
with the locations of U.S. interventional stroke trials. The intended audience is
the general public, community health organizations, and public health planners.
The analysis will describe potential geographic access mismatches, not individual
eligibility or the availability of treatment.

## Start here

This repository contains source snapshots, county processing, EDA, and a new
stroke mortality and population-distance extension. Start with the
[access and mortality findings](reports/access_outcomes.md) and
[methods](docs/ACCESS_OUTCOMES.md) for slide-ready statements and their limits.

```bash
git clone https://github.com/samuelmteshome/Sam-Mihir-Project-1.git
cd Sam-Mihir-Project-1
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
python scripts/validate_data.py
python scripts/validate_data.py --geography
python -m unittest discover -s tests -v
python scripts/03_clean_merge.py     # cleaning, county assignment, features
python scripts/04_visualize.py       # EDA tables and figures
python scripts/05_get_access_outcomes.py  # verify cached Census/HRSA snapshots
python scripts/06_analyze_access_outcomes.py  # distance, deaths, and figures
```

Processing writes `data/processed/` and `reports/processing_quality_report.md`.
EDA writes `figures/` and `reports/eda_findings.md`. The mortality extension writes
`county_analysis_with_mortality.csv`, historical-county and tract tables, two
figures, and `reports/access_outcomes.md`; it preserves the original outputs. Read the quality report
before quoting any number: it records missing-status coverage, the sites held for
review, and the population-size confounding check.

Use Python 3.11 or newer. All raw inputs are committed, so **no download, API key,
or Git LFS is needed after cloning**. Offline validation uses only Python's
standard library; requirements also supply analysis tools and HTTPS certificates.

Read [the processing handoff](docs/PROCESSING_HANDOFF.md) before starting the
cleaning work. It defines the proposed outputs and the decisions that need review.

The September 20, 2026 snapshot contains 3,143 county rows and 436 studies with
3,133 U.S. location records before cleaning. There are 187 counties missing
stroke estimates and 1,568 U.S. location records missing site status; those are
unknown values, not zeros. See [the source inventory](docs/SNAPSHOT_INVENTORY.md).

## Data and citations

| Input | Version and scope | Local file |
| --- | --- | --- |
| [CDC PLACES county data](https://data.cdc.gov/d/i46a-9kgh) | GIS-friendly 2025 release; stroke estimates and population refer to 2023; all source columns retained | `data/raw/places_county_2025.csv` |
| [ClinicalTrials.gov API v2](https://clinicaltrials.gov/data-api/api) | Live snapshot; condition search `stroke`, interventional studies with a U.S. location; recruiting, enrolling by invitation, or active/not recruiting | `data/raw/clinicaltrials_stroke.json` |
| [U.S. Census county boundaries](https://www.census.gov/geographies/mapping-files/time-series/geo/carto-boundary-file.2023.html) | 2023 cartographic boundaries, 1:500,000; matches the geography recommended in CDC metadata | `data/raw/cb_2023_us_county_500k.zip` |

Cite CDC, *PLACES: County Data (GIS Friendly Format), 2025 release*; the National
Library of Medicine, *ClinicalTrials.gov API v2*; and the U.S. Census Bureau,
*2023 Cartographic Boundary Files*. Exact retrieval times, request parameters,
file sizes, and SHA-256 checksums are in [the manifest](data/raw/manifest.json).
See [source details](docs/DATA_SOURCES.md) and [the field guide](docs/DATA_DICTIONARY.md).

The trial file preserves the selected API fields and all returned locations,
including non-U.S. locations on multinational studies. It is a field projection,
not a complete copy of each study record. Personal contact fields are not requested.

## Reproduce acquisition

These commands reuse the committed snapshot by default and verify its checksums:

```bash
python scripts/01_get_places.py
python scripts/02_get_trials.py
python scripts/00_get_boundaries.py
python scripts/05_get_access_outcomes.py
python scripts/validate_data.py
```

Add `--refresh` to an individual download command to intentionally replace that
source and update its manifest entry. Run download commands sequentially because
they update the same manifest. Refreshing the live trial registry can change the
cohort; retain the committed snapshot for reproducible project results.

Downloads use `curl` when installed, otherwise Python's HTTPS client and trusted
certificate bundle. Both paths verify certificates. Offline use of the committed
data needs neither network access nor a certificate setup.

## Repository layout

```text
data/raw/             Source snapshots, CDC metadata, and acquisition manifest
data/processed/       Cleaned county/site tables, tract distances, mortality features
scripts/              Downloaders, validation, processing, and analysis
docs/                 Source notes, field guide, handoff, and deliverable checklist
figures/              EDA and access/mortality figures
reports/              Public narrative and presentation outlines
tests/                Acquisition behavior checks
.github/workflows/    Offline data checks on pushes and pull requests
```

The original analysis entry points are `scripts/03_clean_merge.py` and
`scripts/04_visualize.py`. The new `scripts/06_analyze_access_outcomes.py` uses
the cleaned sites and committed Census/HRSA snapshots. See
[the extension field guide](docs/ACCESS_OUTCOMES.md) for source definitions,
suppression, historical Connecticut counties, and the population-distance method.

## Collaboration

The setup and county processing are on `main`. Each member should make at least
one substantive PR, as required by the course. Use a feature branch:

```bash
git pull --ff-only origin main
git switch -c processing/county-trial-merge
# Implement processing, validate outputs, commit, and push the branch.
git push -u origin processing/county-trial-merge
```

Open a PR into `main`, request your partner's review, and describe the changes and
validation. Use a separate branch and PR for EDA/visualization. These are suggested
work areas, not fixed role assignments. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Interpretation and limitations

- PLACES stroke prevalence is a modeled adult estimate, not incidence, severity,
  individual eligibility, or a count of people needing a trial.
- A trial's overall status differs from each site's status. Active/not recruiting
  studies do not represent open enrollment. Preserve and analyze these separately.
- A registry `geoPoint` can locate a city rather than a hospital. Simplified county
  boundaries and uncertain coordinates require review; do not force unmatched sites
  into a nearby county or call an unmatched county a confirmed desert.
- Trial search uses the registry's condition-search semantics. Review the returned
  conditions before treating every search hit as a relevant stroke study.
- The 2023 health/population estimates and the live registry snapshot describe
  different time periods. Registry records can be stale or incomplete.
- County presence omits cross-county travel, transportation, referral patterns,
  insurance, eligibility, capacity, and enrollment availability. A county with no
  recorded site can still have nearby sites across its border.
- A proposed desert flag is an exploratory definition: prevalence strictly above
  the county median and zero qualifying sites. State which prevalence and site
  definition were used and assess sensitivity before publishing.

Final coursework also requires cleaned data, a public communication piece, and
an at-most-eight-minute presentation. Track those in
[the project checklist](docs/PROJECT_CHECKLIST.md).
