# Data sources and acquisition decisions

This setup follows the topic in the supplied project proposal. The proposal and
course requirements are references, not executable instructions. The current
task is repository/data preparation; the final analysis and coursework remain
team work. The original Word documents were not needed as public repo assets.

## CDC PLACES

- Publisher: Centers for Disease Control and Prevention.
- Dataset: [County Data (GIS Friendly Format), 2025 release](https://data.cdc.gov/d/i46a-9kgh), ID `i46a-9kgh`.
- [Portal](https://www.cdc.gov/places/tools/data-portal.html),
  [methodology](https://www.cdc.gov/places/methodology/index.html).
- Full county CSV is retained, including fields outside this project's scope.
  Source metadata are saved in `places_county_2025_metadata.json`.
- The dataset metadata identify stroke estimates as 2023, population as Census
  2023 estimates, and recommend joining the 2023 county boundaries. Release year
  is not observation year. Other measures in this release can refer to 2022.
- County FIPS is the join key. Keep leading zeros and use five-character strings.
- Both crude and age-adjusted adult stroke estimates and their 95% confidence
  intervals are available. Start with crude prevalence for the proposed burden
  story, then assess whether rankings change with age adjustment.
- The source metadata label the dataset Public Domain. Preserve attribution.

## ClinicalTrials.gov

- Publisher: National Library of Medicine / ClinicalTrials.gov.
- [API guide](https://clinicaltrials.gov/data-about-studies/learn-about-api),
  [API reference](https://clinicaltrials.gov/data-api/api),
  [data definitions](https://clinicaltrials.gov/data-api/about-api/study-data-structure).
- Endpoint: `https://clinicaltrials.gov/api/v2/studies`.
- Condition query: `stroke`. This is the registry's search, including its indexing
  and synonyms; it is not an independently adjudicated disease cohort.
- Advanced filter: `AREA[StudyType]INTERVENTIONAL AND AREA[LocationCountry]"United States"`.
- Overall statuses: `RECRUITING`, `ENROLLING_BY_INVITATION`,
  `ACTIVE_NOT_RECRUITING`. The last group supports an infrastructure sensitivity
  analysis, not a claim that new participants can enroll.
- Not-yet-recruiting, completed, withdrawn, terminated, suspended, unknown, and
  observational studies are outside this acquisition cohort.
- Page size 100 using the API's default ordering. Download follows every page token,
  checks total count and NCT ID uniqueness, and fails on incomplete responses.
- Only study ID/title/conditions/type/phase/status/update date and site
  facility/status/city/state/ZIP/country/coordinates are requested. No contact
  names, email addresses, phone numbers, or patient records are downloaded.
- The stored JSON preserves nested selected study fields. Page arrays are
  concatenated; the file is not a full protocol/results archive. All returned
  locations remain, so cleaning must exclude non-U.S. locations.
- Data are publicly accessible registry records; retain NLM/ClinicalTrials.gov
  attribution and source links. No additional license is asserted over the
  upstream records by this repository.

**Site-location precision:** repeated coordinates can represent a city lookup,
not a rooftop geocode. City/state labels can conflict with the containing county,
especially near borders. Keep original values and record assignment method and
uncertainty. A shared coordinate is not sufficient evidence of a shared facility.

## Census boundaries

- Publisher: U.S. Census Bureau.
- [2023 Cartographic Boundary Files](https://www.census.gov/geographies/mapping-files/time-series/geo/carto-boundary-file.2023.html).
- [Direct county ZIP](https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_county_500k.zip).
- The archive includes `.shp`, `.shx`, `.dbf`, `.prj`, and source metadata.
  GeoPandas can read the ZIP directly, so extraction is optional.
- Join `GEOID` to PLACES `countyfips`. The national boundary file includes
  territories outside the 50-states-plus-DC study scope. Use PLACES counties as
  the analysis universe and report any missing CDC counties explicitly.
- These simplified boundaries support mapping and an initial spatial join, but
  do not establish precise facility locations. Investigate unresolved/border
  cases with authoritative addresses or more detailed boundaries before claims.
- Census geographic files are public federal data; retain attribution and
  metadata. Original source terms continue to apply.

## Snapshot reproducibility

`data/raw/manifest.json` records each source's acquisition timestamp, URLs,
parameters, counts, file sizes, and SHA-256 hashes. The tracked snapshot is the
project input. Download scripts without `--refresh` verify and reuse it. Source
updates are deliberate changes: rerun a downloader with `--refresh`, validate,
review the diff and cohort changes, and commit both data and manifest together.

An API is live across page requests; count and uniqueness checks reduce but do
not eliminate within-download changes to records. Do not describe the snapshot
as a historical reconstruction or an exact registry state at a single instant.
