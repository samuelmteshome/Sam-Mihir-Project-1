"""Download the 2023 county cartographic boundaries recommended by CDC metadata."""

import io
from zipfile import ZipFile
from _common import arguments, fetch, save_snapshot, use_cached

NAME = "cb_2023_us_county_500k.zip"
URL = f"https://www2.census.gov/geo/tiger/GENZ2023/shp/{NAME}"


def main():
    args = arguments(__doc__)
    if use_cached("census_boundaries", args.refresh):
        return
    payload = fetch(URL)
    with ZipFile(io.BytesIO(payload)) as archive:
        if archive.testzip() is not None:
            raise ValueError("Corrupt Census archive")
        for extension in ("shp", "shx", "dbf", "prj"):
            if not any(n.endswith("." + extension) for n in archive.namelist()):
                raise ValueError(f"Missing {extension} in Census archive")
    save_snapshot("census_boundaries", {NAME: payload}, {
        "title": "U.S. Census 2023 County Cartographic Boundaries, 1:500,000",
        "source_url": URL, "geography_year": 2023,
        "transformations": "None; ZIP saved verbatim, including source metadata and projection.",
        "caution": "Simplified cartographic boundaries, not precise geocoding boundaries. Review ambiguous or unmatched points.",
    })


if __name__ == "__main__":
    main()
