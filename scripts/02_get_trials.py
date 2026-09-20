"""Retrieve all pages of the selected U.S. interventional stroke study cohort."""

import json
from _common import arguments, fetch, json_bytes, make_url, save_snapshot, use_cached

BASE = "https://clinicaltrials.gov/api/v2/studies"
STATUSES = ["RECRUITING", "ENROLLING_BY_INVITATION", "ACTIVE_NOT_RECRUITING"]
PARAMS = {
    "query.cond": "stroke",
    "filter.advanced": 'AREA[StudyType]INTERVENTIONAL AND AREA[LocationCountry]"United States"',
    "filter.overallStatus": ",".join(STATUSES),
    "fields": ",".join([
        "NCTId", "BriefTitle", "Condition", "StudyType", "Phase", "OverallStatus",
        "LastUpdatePostDate", "LocationFacility", "LocationStatus", "LocationCity",
        "LocationState", "LocationZip", "LocationCountry", "LocationGeoPoint",
    ]),
    "format": "json", "pageSize": 100, "countTotal": "true",
}


def download_studies(fetcher=fetch):
    studies, tokens = [], set()
    params = dict(PARAMS)
    expected, pages = None, 0
    while True:
        page = json.loads(fetcher(make_url(BASE, params)))
        if not isinstance(page.get("studies"), list):
            raise ValueError("Missing studies array in registry response.")
        if expected is None:
            expected = page["totalCount"]
        elif page.get("totalCount", expected) != expected:
            raise ValueError("Registry count changed during acquisition; rerun for a consistent snapshot.")
        studies.extend(page["studies"])
        pages += 1
        print(f"Trial page {pages}: {len(studies)} / {expected}")
        token = page.get("nextPageToken")
        if not token:
            break
        if token in tokens:
            raise ValueError("Registry returned a repeated pagination token.")
        tokens.add(token)
        params["pageToken"] = token
    ids = [s["protocolSection"]["identificationModule"]["nctId"] for s in studies]
    if not studies or len(studies) != expected or len(set(ids)) != len(ids):
        raise ValueError("Incomplete or duplicate registry response; snapshot not saved.")
    return {"totalCount": expected, "studies": studies}, pages


def main():
    args = arguments(__doc__)
    if use_cached("clinicaltrials", args.refresh):
        return
    snapshot, pages = download_studies()
    save_snapshot("clinicaltrials", {"clinicaltrials_stroke.json": json_bytes(snapshot)}, {
        "title": "ClinicalTrials.gov U.S. interventional stroke trial snapshot",
        "source_url": BASE, "query_parameters": PARAMS, "study_count": snapshot["totalCount"],
        "pages_fetched": pages,
        "transformations": "API field projection; study arrays concatenated across pages; no study or location cleaning. All returned locations retained.",
    })


if __name__ == "__main__":
    main()
