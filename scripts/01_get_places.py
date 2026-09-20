"""Download the full GIS-friendly 2025 county release, with its field metadata."""

import csv
import io
import json
from _common import arguments, fetch, make_url, save_snapshot, use_cached

DATASET = "i46a-9kgh"
BASE = f"https://data.cdc.gov/resource/{DATASET}"


def main():
    args = arguments(__doc__)
    if use_cached("cdc_places", args.refresh):
        return
    params = {"$limit": 10000, "$order": "countyfips"}
    url = make_url(BASE + ".csv", params)
    payload = fetch(url)
    rows = list(csv.DictReader(io.StringIO(payload.decode("utf-8-sig"))))
    count_url = make_url(BASE + ".json", {"$select": "count(*)"})
    expected = int(json.loads(fetch(count_url))[0]["count"])
    if len(rows) != expected or not rows:
        raise ValueError(f"Incomplete CDC response: {len(rows)} / {expected}")
    required = {"countyfips", "totalpopulation", "totalpop18plus", "stroke_crudeprev", "stroke_adjprev"}
    if not required.issubset(rows[0]):
        raise ValueError("CDC schema changed; inspect fields before saving.")
    metadata_url = f"https://data.cdc.gov/api/views/{DATASET}.json"
    metadata = fetch(metadata_url)
    if "2025" not in json.loads(metadata)["name"]:
        raise ValueError("Unexpected CDC release; inspect metadata before saving.")
    save_snapshot("cdc_places", {
        "places_county_2025.csv": payload,
        "places_county_2025_metadata.json": metadata,
    }, {
        "title": "CDC PLACES County Data (GIS Friendly Format), 2025 release",
        "dataset_id": DATASET, "source_url": url, "metadata_url": metadata_url,
        "count_url": count_url, "row_count": len(rows),
        "release_year": 2025, "stroke_estimate_year": 2023, "population_year": 2023,
        "transformations": "None; full CSV response and source metadata saved verbatim.",
    })


if __name__ == "__main__":
    main()
