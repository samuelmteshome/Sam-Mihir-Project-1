# Input field guide

This guide covers fields needed for the planned analysis. The complete CDC field
descriptions are in `data/raw/places_county_2025_metadata.json`. Missing values
must remain missing until a documented processing rule resolves them.

## PLACES county CSV

One row per source county; individual measure estimates can be missing. Read
FIPS as text.

| Field | Meaning / handling |
| --- | --- |
| `countyfips` | Five-digit county or county-equivalent FIPS; join to Census `GEOID` |
| `countyname` | Source county name; not a unique join key |
| `stateabbr`, `statedesc` | State abbreviation and name |
| `totalpopulation` | Census 2023 estimated total population, all ages |
| `totalpop18plus` | Census 2023 estimated population age 18+ |
| `stroke_crudeprev` | 2023 modeled crude stroke prevalence among adults, percent |
| `stroke_crude95ci` | Source interval string for crude prevalence; parse into bounds |
| `stroke_adjprev` | 2023 modeled age-adjusted adult stroke prevalence, percent |
| `stroke_adj95ci` | Source interval string for age-adjusted prevalence |
| `geolocation` | County reference point, not its boundary and not a trial site |

The CSV also contains other health measures; retaining them does not imply that
they are included in this project's analysis. See source metadata for their years.

## Trial JSON

The root contains `totalCount` and `studies`. Each study contains
`protocolSection`; paths below are relative to it.

| Path | Meaning / handling |
| --- | --- |
| `identificationModule.nctId` | Unique study identifier, e.g. `NCT########` |
| `identificationModule.briefTitle` | Study title; useful for cohort review |
| `conditionsModule.conditions` | Condition list returned by the registry |
| `statusModule.overallStatus` | Study-wide status, not each site's status |
| `statusModule.lastUpdatePostDateStruct.date` | Registry update date; retain for staleness audit |
| `designModule.studyType` | Expected `INTERVENTIONAL` |
| `designModule.phases` | List; `NA` is possible and is not a missing value |
| `contactsLocationsModule.locations` | List of site records; flatten one per row |
| `locations[].facility` | Reported facility name, can be absent or inconsistent |
| `locations[].status` | Site status, sometimes absent; missing is not recruiting |
| `locations[].city`, `.state`, `.zip`, `.country` | Source geographic labels; keep ZIP as text |
| `locations[].geoPoint.lat`, `.lon` | Latitude/longitude; may be missing or city-level |

Do not deduplicate solely by `nctId` (a study may have many sites) or solely by
coordinates (different facilities may share a city point). The metric counting
trial/site pairs differs from counting distinct physical facilities.

## Census county ZIP

| Field | Meaning / handling |
| --- | --- |
| `GEOID` | Five-character state + county FIPS join key |
| `STATEFP`, `COUNTYFP` | Two- and three-character component codes |
| `NAME`, `NAMELSAD` | County name labels |
| `geometry` | County polygon/multipolygon interpreted using the `.prj` CRS |

Convert the county geometry to the point CRS before joining. For lon/lat registry
points, use `EPSG:4326` and GeoPandas `points_from_xy(lon, lat)` (longitude first).

## Proposed processed schema

These files do not exist yet; this is the contract for the processing PR.

`trial_sites.csv`: `nct_id`, `trial_title`, `overall_status`, `site_status`,
`facility`, `city`, `state`, `zip`, `country`, `latitude`, `longitude`,
`county_fips`, `assignment_method`, `assignment_review_needed`,
`last_update_post_date`. Preserve source-row identifiers to trace exclusions.

`county_analysis.csv`: `county_fips`, `county_name`, `state_abbr`,
`total_population`, `adult_population`, `stroke_crude_pct`, `stroke_age_adjusted_pct`,
confidence interval bounds, `recruiting_trial_site_count`,
`active_trial_site_count`, `unique_facility_count`, `trial_sites_per_100k`,
`above_median_stroke`, `potential_trial_desert`.

`unmatched_sites.csv`: source site fields and an explicit exclusion/assignment
failure reason. `quality_report.json`: input/output counts, exclusions,
deduplication counts, joins, missingness, and metric definitions.

Agree on final column names and definitions before EDA; update this document to
match the implementation. Do not create empty fake analysis tables as results.
