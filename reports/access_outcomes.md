# Stroke mortality and distance to trial sites

## Slide-ready statements

- **An estimated 14.3% of U.S. residents live more than 50 straight-line miles from a recorded active stroke trial site.** Estimate uses 2020 Census tract population centers and the September 2026 registry snapshot.
- **An estimated 90% of U.S. residents live within 62.5 straight-line miles of a recorded active stroke trial site.**
- **Among counties with published counts, 49.6% of average annual stroke deaths occurred among residents of counties with no recorded active trial site.** Deaths: 2021–2023; trial sites: September 2026.

Mortality denominator: 158,301 published annual-average deaths across 1,995 counties; 1,148 counties have suppressed/missing counts. The numerator is 78,543. These are sums of source-reported rounded annual averages, not exact three-year totals.

Do not shorten the mortality statement to a percentage of **all** U.S. stroke deaths. Missing counts are not zeros. County site presence does not show how far deceased people lived from a site.

## Distance and site-definition sensitivity

| Site definition | More than 25 mi | More than 50 mi | More than 100 mi | Median mi | 90th percentile mi |
|---|---:|---:|---:|---:|---:|
| active | 30.2% | 14.3% | 3.8% | 12.0 | 62.5 |
| recruiting | 30.8% | 15.0% | 3.9% | 12.2 | 63.9 |
| active_plus_unknown_sensitivity | 22.8% | 8.8% | 2.2% | 8.7 | 46.4 |

The active-plus-unknown row is an optimistic sensitivity scenario; unknown site status is not confirmed activity or enrollment availability.

## Metropolitan context

| County classification | Population >50 mi from active site | Counties with death counts | Published deaths in no-site counties |
|---|---:|---:|---:|
| metro | 8.0% | 1024 | 41.6% |
| nonmetro | 54.9% | 963 | 97.9% |
| unavailable | 0.0% | 8 | 25.8% |

Metro/nonmetro uses USDA 2023 Rural-Urban Continuum Codes carried in AHRF. Nonmetro is a county classification, not a measure of each resident's rurality. Historical Connecticut counties have no 2023 code. Suppression particularly affects small counties.

## Interpretation

These are geographic descriptions of a broad stroke-related interventional research cohort, including prevention and rehabilitation. They do not identify thrombolysis-capable hospitals or demonstrate that rural residents were excluded from enrollment. They cannot establish different tPA treatment windows, treatment effectiveness, or a causal effect of trial-site location on mortality.

Population: all ages, 331,449,281 residents in 50 states + DC. Distances are approximate, not road travel times; registry coordinates may represent cities. Active sites include active/not recruiting sites. See the recruiting-only sensitivity for enrollment-oriented wording.

## Reproduce and inspect

Run `python scripts/06_analyze_access_outcomes.py` after the existing cleaning pipeline. See [methods and field guide](../docs/ACCESS_OUTCOMES.md), [machine-readable results](access_outcomes_summary.json), and the two new figures. Data acquisition URLs, hashes, periods, and source field definitions are in the raw manifest and archived HRSA documentation.
