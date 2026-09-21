"""Acquire population centers and county mortality counts; cached/offline by default."""

import csv
import hashlib
import io
from zipfile import ZipFile

from _common import arguments, fetch, save_snapshot, use_cached

CENTERS_URL = "https://www2.census.gov/geo/docs/reference/cenpop2020/tract/CenPop2020_Mean_TR.txt"
BOUNDARIES_URL = "https://www2.census.gov/geo/tiger/GENZ2020/shp/cb_2020_us_county_500k.zip"
AHRF_URL = "https://data.hrsa.gov/DataDownload/AHRF/AHRF_2024-2025_CSV.zip"
GUIDE_URL = "https://data.hrsa.gov/DataDownload/AHRF/AHRF_USER_TECH_2024-2025.zip"
AHRF_FIELDS = [
    "fips_st_cnty", "st_name", "st_name_abbrev", "cnty_name",
    "cerbrvsc_dis_deth_3yr_23", "cerbrvsc_dis_deth_3yr_22",
    "rural_urban_contnm_23", "cens_popn_20", "cens_rural_popn_20",
]


def project_ahrf(payload):
    """Retain only public NCHS/Census/USDA fields, preserving blank suppression."""
    with ZipFile(io.BytesIO(payload)) as archive:
        names = [n for n in archive.namelist() if n.endswith("/AHRF2025.csv")]
        if len(names) != 1:
            raise ValueError("Expected exactly one full AHRF2025.csv")
        with io.TextIOWrapper(archive.open(names[0]), encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            if not set(AHRF_FIELDS).issubset(reader.fieldnames or []):
                raise ValueError("AHRF schema changed")
            rows = [{key: row[key] for key in AHRF_FIELDS} for row in reader]
    ids = [r["fips_st_cnty"] for r in rows]
    if not ids or len(ids) != len(set(ids)) or any(len(i) != 5 or not i.isdigit() for i in ids):
        raise ValueError("Invalid or duplicate AHRF county FIPS")
    for row in rows:
        for key in ("cerbrvsc_dis_deth_3yr_23", "cerbrvsc_dis_deth_3yr_22"):
            if row[key] and (not row[key].isdigit() or int(row[key]) < 10):
                raise ValueError("Unexpected AHRF mortality value or suppression encoding")
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=AHRF_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(sorted(rows, key=lambda r: r["fips_st_cnty"]))
    return output.getvalue().encode(), len(rows)


def main():
    args = arguments(__doc__)
    if not use_cached("census_population_centers_2020", args.refresh):
        payload = fetch(CENTERS_URL)
        rows = list(csv.DictReader(io.StringIO(payload.decode("utf-8-sig"))))
        if not rows or not {"STATEFP", "COUNTYFP", "TRACTCE", "POPULATION", "LATITUDE", "LONGITUDE"}.issubset(rows[0]):
            raise ValueError("Unexpected population-center schema")
        save_snapshot("census_population_centers_2020", {"tract_population_centers_2020.txt": payload}, {
            "title": "2020 Census tract population-weighted mean centers",
            "source_url": CENTERS_URL, "row_count": len(rows), "population_year": 2020,
            "transformations": "None; national file preserved verbatim, including territories.",
        })
    if not use_cached("census_boundaries_2020", args.refresh):
        payload = fetch(BOUNDARIES_URL)
        with ZipFile(io.BytesIO(payload)) as archive:
            if archive.testzip() is not None or not any(n.endswith('.shp') for n in archive.namelist()):
                raise ValueError("Invalid county boundary archive")
        save_snapshot("census_boundaries_2020", {"cb_2020_us_county_500k.zip": payload}, {
            "title": "2020 Census county cartographic boundaries, 1:500,000",
            "source_url": BOUNDARIES_URL, "transformations": "None; used to retain historical Connecticut counties.",
        })
    if not use_cached("hrsa_ahrf_mortality_2025", args.refresh):
        payload = fetch(AHRF_URL)
        projected, count = project_ahrf(payload)
        save_snapshot("hrsa_ahrf_mortality_2025", {
            "ahrf_stroke_mortality_2025.csv": projected,
            "ahrf_documentation_2025.zip": fetch(GUIDE_URL),
        }, {
            "title": "HRSA AHRF 2024–2025: county cerebrovascular deaths and rural context",
            "source_url": AHRF_URL, "documentation_url": GUIDE_URL,
            "upstream_archive_sha256": hashlib.sha256(payload).hexdigest(),
            "row_count": count, "fields": AHRF_FIELDS,
            "mortality_period": "2021–2023 (primary); 2020–2022 (comparison)",
            "transformations": "CSV field projection, FIPS sort, LF serialization; original values and blanks retained. Full archive not committed.",
        })


if __name__ == "__main__":
    main()
