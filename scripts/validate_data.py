"""Offline integrity and basic schema checks for the committed source snapshots."""

from collections import Counter
import argparse
import csv
import hashlib
import json
import math
import re
from zipfile import ZipFile
from _common import RAW, read_manifest


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate():
    manifest = read_manifest()
    require(manifest.get("schema_version") == 1, "Unsupported manifest schema")
    require(set(manifest["sources"]) == {"cdc_places", "clinicaltrials", "census_boundaries"},
            "Download all three sources first")
    for source in manifest["sources"].values():
        for name, expected in source["files"].items():
            payload = (RAW / name).read_bytes()
            require(len(payload) == expected["bytes"], f"Size mismatch: {name}")
            require(hashlib.sha256(payload).hexdigest() == expected["sha256"],
                    f"Checksum mismatch: {name}")

    with (RAW / "places_county_2025.csv").open(encoding="utf-8-sig", newline="") as handle:
        places = list(csv.DictReader(handle))
    require(len(places) == manifest["sources"]["cdc_places"]["row_count"], "CDC count mismatch")
    required = {"countyfips", "countyname", "stateabbr", "totalpopulation", "totalpop18plus",
                "stroke_crudeprev", "stroke_adjprev", "stroke_crude95ci", "stroke_adj95ci"}
    require(bool(places) and required.issubset(places[0]), "Missing CDC fields")
    fips = [row["countyfips"] for row in places]
    require(all(re.fullmatch(r"\d{5}", f) for f in fips), "Invalid CDC county FIPS")
    require(len(fips) == len(set(fips)), "Duplicate CDC counties")
    for row in places:
        for name in ("stroke_crudeprev", "stroke_adjprev"):
            if row[name]:
                require(0 <= float(row[name]) <= 100, f"Invalid prevalence: {row['countyfips']}")
        for name in ("totalpopulation", "totalpop18plus"):
            if row[name]:
                require(math.isfinite(float(row[name])) and float(row[name]) > 0,
                        f"Invalid population: {row['countyfips']}")

    snapshot = json.loads((RAW / "clinicaltrials_stroke.json").read_text())
    studies = snapshot["studies"]
    require(len(studies) == snapshot["totalCount"] == manifest["sources"]["clinicaltrials"]["study_count"],
            "Trial count mismatch")
    ids, us_locations, statuses = [], [], Counter()
    location_count = 0
    for study in studies:
        protocol = study["protocolSection"]
        nct_id = protocol["identificationModule"]["nctId"]
        ids.append(nct_id)
        require(re.fullmatch(r"NCT\d{8}", nct_id), f"Invalid NCT ID: {nct_id}")
        require(protocol["designModule"]["studyType"] == "INTERVENTIONAL", f"Wrong study type: {nct_id}")
        status = protocol["statusModule"]["overallStatus"]
        require(status in {"RECRUITING", "ENROLLING_BY_INVITATION", "ACTIVE_NOT_RECRUITING"},
                f"Out-of-scope study status: {nct_id}")
        statuses[status] += 1
        sites = protocol.get("contactsLocationsModule", {}).get("locations", [])
        location_count += len(sites)
        us = [site for site in sites if site.get("country") == "United States"]
        require(bool(us), f"Study has no returned U.S. site: {nct_id}")
        us_locations.extend(us)
        for site in sites:
            point = site.get("geoPoint")
            if point:
                require(-90 <= point["lat"] <= 90 and -180 <= point["lon"] <= 180,
                        f"Invalid coordinates: {nct_id}")
    require(len(ids) == len(set(ids)), "Duplicate NCT IDs")
    with ZipFile(RAW / "cb_2023_us_county_500k.zip") as archive:
        require(archive.testzip() is None, "Corrupt Census ZIP")
        for suffix in (".shp", ".shx", ".dbf", ".prj"):
            require(any(name.endswith(suffix) for name in archive.namelist()), f"Missing {suffix}")

    summary = {
        "places_counties": len(places),
        "places_states_or_dc": len({r["stateabbr"] for r in places}),
        "places_missing_crude_stroke": sum(not r["stroke_crudeprev"] for r in places),
        "places_missing_age_adjusted_stroke": sum(not r["stroke_adjprev"] for r in places),
        "places_missing_stroke_by_state": dict(sorted(Counter(
            r["stateabbr"] for r in places if not r["stroke_crudeprev"]
        ).items())),
        "trials": len(studies), "study_status_counts": dict(sorted(statuses.items())),
        "all_location_records": location_count, "us_location_records_before_cleaning": len(us_locations),
        "us_locations_missing_coordinates": sum(not r.get("geoPoint") for r in us_locations),
        "us_locations_missing_facility": sum(not r.get("facility") for r in us_locations),
        "us_site_status_counts": dict(sorted(Counter(r.get("status", "MISSING") for r in us_locations).items())),
        "note": "Source inventory only; location rows are not deduplicated facilities or validated county assignments.",
    }
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--geography", action="store_true", help="Also check county geometries and FIPS coverage (requires geopandas).")
    args = parser.parse_args()
    summary = validate()
    if args.geography:
        import geopandas as gpd

        boundaries = gpd.read_file(RAW / "cb_2023_us_county_500k.zip")
        with (RAW / "places_county_2025.csv").open(encoding="utf-8-sig", newline="") as handle:
            fips = {row["countyfips"] for row in csv.DictReader(handle)}
        missing = sorted(fips - set(boundaries["GEOID"]))
        require(not missing, f"CDC counties missing from boundaries: {missing}")
        require(boundaries["GEOID"].is_unique, "Duplicate boundary GEOID")
        require(boundaries.crs is not None, "Missing boundary CRS")
        require(boundaries.geometry.notna().all() and boundaries.is_valid.all(), "Invalid county geometry")
        summary["geography"] = {
            "boundary_records": len(boundaries), "crs": str(boundaries.crs),
            "places_counties_without_boundary": missing,
            "boundaries_outside_places": len(set(boundaries["GEOID"]) - fips),
        }
    print(json.dumps(summary, indent=2))
    print("PASS: source checksums, counts, core schemas, cohort filters, and boundary ZIP")
