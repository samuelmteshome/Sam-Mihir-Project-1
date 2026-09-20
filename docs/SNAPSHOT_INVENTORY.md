# Source snapshot inventory

Downloaded September 20, 2026 UTC. Exact timestamps and byte-level hashes are in
`data/raw/manifest.json`. This is an input audit, not processed analysis or evidence
of clinical trial deserts. Regenerate the checks with:

```bash
python scripts/validate_data.py
python scripts/validate_data.py --geography
```

The second command requires the analysis dependencies in `requirements.txt`.

| Input measure | Observed count |
| --- | ---: |
| PLACES county rows | 3,143 |
| States plus DC represented | 51 |
| County rows with a crude stroke estimate | 2,956 |
| County rows missing crude and age-adjusted stroke estimates | 187 |
| Interventional studies in the selected cohort | 436 |
| Studies recruiting | 333 |
| Studies enrolling by invitation | 21 |
| Studies active, not recruiting | 82 |
| All returned location records, including non-U.S. | 6,915 |
| U.S. location records before cleaning/deduplication | 3,133 |
| U.S. location records missing coordinates | 5 |
| U.S. location records missing facility name | 0 |
| County boundary records, including territories | 3,235 |
| PLACES county IDs without a matching boundary | 0 |

Missing stroke estimates cover all 120 counties in Kentucky and all 67 in
Pennsylvania. A state-wide missingness pattern matters for the story: neither
state can be ranked for stroke burden using these values. They must not be shown
as zero prevalence or assigned a false desert flag merely because data are missing.

## U.S. site status values before cleaning

| Site status | Location rows |
| --- | ---: |
| Recruiting | 1,348 |
| Active, not recruiting | 52 |
| Not yet recruiting | 66 |
| Completed | 1 |
| Suspended | 5 |
| Terminated | 15 |
| Withdrawn | 78 |
| Missing | 1,568 |

A trial with a recruiting overall status can contain a withdrawn or closed site.
An invitation-only study can have missing site-level status. Do not substitute
the overall study status for missing site status without a separately labeled
sensitivity analysis. These are location rows, not unique hospitals or confirmed
recruiting locations in the final cohort.

## Geography audit

The downloaded boundaries use EPSG:4269. All source PLACES county FIPS codes match
boundary `GEOID` values, all boundary IDs are unique, and all geometries passed
GeoPandas validity checks. The boundary file has 92 rows outside the PLACES table:
91 territorial county equivalents and Loving County, Texas (`48301`). Keep the source PLACES
table as the starting analysis universe and document its coverage limitation.

Simplified geometry validity does not establish registry coordinate accuracy or
validate the future site-to-county assignments. That audit belongs in processing.
