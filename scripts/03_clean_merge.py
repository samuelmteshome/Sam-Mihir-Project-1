"""Clean, merge, and engineer county-level stroke trial access features.

Implements docs/PROCESSING_HANDOFF.md against the committed snapshots in
data/raw/. Raw inputs are read only; nothing here overwrites them.

    python scripts/03_clean_merge.py

Outputs (data/processed/):
    county_analysis.csv             one row per PLACES county, features attached
    trial_sites_clean.csv           deduplicated trial/site pairs, county assigned
    site_assignment_review.csv      sites needing manual review, never silently dropped
    population_stratified_check.csv confounding check described below
    state_summary.csv               state rollup
Report:
    reports/processing_quality_report.md

Two site cohorts are carried side by side, per the handoff:
    recruiting  overall study status RECRUITING *and* site status RECRUITING
    active      site status RECRUITING, ENROLLING_BY_INVITATION or ACTIVE_NOT_RECRUITING
Missing site status is never inferred as recruiting; it is reported as unknown.
"""
import json
import re
import unicodedata
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "reports"

TERRITORY_FIPS = {"60", "66", "69", "72", "78"}
RECRUITING_SITE = {"RECRUITING"}
ACTIVE_SITE = {"RECRUITING", "ENROLLING_BY_INVITATION", "ACTIVE_NOT_RECRUITING"}

# Conditions matching the text "stroke" that are not cerebrovascular disease.
# Documented by explicit condition string, never a title substring filter.
NON_CEREBROVASCULAR = ("heat stroke", "heat exhaustion", "sunstroke")

USPS_TO_NAME = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois",
    "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan",
    "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana",
    "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey",
    "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota",
    "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
    "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia",
    "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}

audit = {}


# ---------------------------------------------------------------------------
# 1. PLACES
# ---------------------------------------------------------------------------
def load_places() -> pd.DataFrame:
    cols = ["countyfips", "countyname", "stateabbr", "statedesc",
            "totalpopulation", "totalpop18plus",
            "stroke_crudeprev", "stroke_crude95ci",
            "stroke_adjprev", "stroke_adj95ci"]
    df = pd.read_csv(RAW / "places_county_2025.csv",
                     dtype={"countyfips": "string"}, usecols=cols)
    df["countyfips"] = df["countyfips"].str.zfill(5)
    df["state_fips"] = df["countyfips"].str[:2]

    for col in ("totalpopulation", "totalpop18plus", "stroke_crudeprev", "stroke_adjprev"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    assert df["countyfips"].is_unique, "PLACES has duplicate county FIPS"
    assert df["countyfips"].str.len().eq(5).all(), "non-five-character FIPS present"

    missing = df["stroke_crudeprev"].isna()
    audit["places_counties"] = len(df)
    audit["places_missing_prevalence"] = int(missing.sum())
    audit["places_missing_states"] = df.loc[missing, "stateabbr"].value_counts().to_dict()
    audit["places_population_missing"] = int(df["totalpopulation"].isna().sum())
    return df


# ---------------------------------------------------------------------------
# 2-4. Trial locations: flatten, scope, cohort review, deduplicate
# ---------------------------------------------------------------------------
def normalize_facility(value) -> str:
    """Casefold, strip accents and punctuation, collapse whitespace."""
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^\w\s]", " ", text.casefold())
    return re.sub(r"\s+", " ", text).strip()


def load_sites() -> pd.DataFrame:
    studies = json.loads((RAW / "clinicaltrials_stroke.json").read_text())["studies"]
    rows = []
    for study in studies:
        ps = study["protocolSection"]
        ident = ps.get("identificationModule", {})
        status = ps.get("statusModule", {})
        design = ps.get("designModule", {})
        for loc in ps.get("contactsLocationsModule", {}).get("locations", []) or []:
            gp = loc.get("geoPoint") or {}
            rows.append({
                "nct_id": ident.get("nctId"),
                "brief_title": ident.get("briefTitle"),
                "overall_status": status.get("overallStatus"),
                "last_update": (status.get("lastUpdatePostDateStruct") or {}).get("date"),
                "study_type": design.get("studyType"),
                "phase": "|".join(design.get("phases", []) or []),
                "conditions": "|".join(ps.get("conditionsModule", {}).get("conditions", []) or []),
                "facility": loc.get("facility"),
                "city": loc.get("city"),
                "state": loc.get("state"),
                "zip": loc.get("zip"),
                "country": loc.get("country"),
                "site_status": loc.get("status"),
                "lat": gp.get("lat"),
                "lon": gp.get("lon"),
            })
    df = pd.DataFrame(rows)
    audit["studies_in_snapshot"] = len(studies)
    audit["location_rows_all_countries"] = len(df)

    df = df[df["country"] == "United States"].copy()
    audit["location_rows_us"] = len(df)
    audit["site_status_missing"] = int(df["site_status"].isna().sum())
    audit["site_status_counts"] = df["site_status"].fillna("UNKNOWN").value_counts().to_dict()
    audit["coords_missing"] = int(df["lat"].isna().sum())

    excluded = df["conditions"].str.lower().apply(
        lambda t: any(term in t for term in NON_CEREBROVASCULAR))
    audit["excluded_condition_nct_ids"] = sorted(df.loc[excluded, "nct_id"].unique().tolist())
    df = df[~excluded].copy()

    # Deduplicate on study + normalized facility identity, never on coordinates:
    # distinct facilities in one city can share city-level coordinates.
    df["facility_key"] = df["facility"].apply(normalize_facility)
    df["city_key"] = df["city"].apply(normalize_facility)
    audit["blank_facility_names"] = int((df["facility_key"] == "").sum())

    before = len(df)
    df = df.drop_duplicates(subset=["nct_id", "facility_key", "city_key", "state"]).copy()
    audit["duplicate_pairs_removed"] = before - len(df)
    audit["trial_site_pairs"] = len(df)

    df["is_recruiting_site"] = (
        df["site_status"].isin(RECRUITING_SITE) & df["overall_status"].eq("RECRUITING"))
    df["is_active_site"] = df["site_status"].isin(ACTIVE_SITE)
    audit["recruiting_pairs"] = int(df["is_recruiting_site"].sum())
    audit["active_pairs"] = int(df["is_active_site"].sum())
    return df


# ---------------------------------------------------------------------------
# 5. Spatial assignment
# ---------------------------------------------------------------------------
def load_counties() -> gpd.GeoDataFrame:
    gdf = gpd.read_file(RAW / "cb_2023_us_county_500k.zip")
    gdf = gdf[["GEOID", "NAME", "STATEFP", "STUSPS", "geometry"]].rename(
        columns={"GEOID": "countyfips", "NAME": "county_poly",
                 "STATEFP": "state_fips", "STUSPS": "state_usps"})
    audit["boundary_polygons_all"] = len(gdf)
    gdf = gdf[~gdf["state_fips"].isin(TERRITORY_FIPS)].copy()
    audit["boundary_polygons_in_scope"] = len(gdf)
    return gdf


def assign_counties(sites: pd.DataFrame, counties: gpd.GeoDataFrame):
    """Point-in-polygon in a common CRS. Unmatched and ambiguous rows are kept."""
    located = sites.dropna(subset=["lat", "lon"]).copy()
    pts = gpd.GeoDataFrame(
        located, geometry=gpd.points_from_xy(located["lon"], located["lat"]),
        crs="EPSG:4326").to_crs(counties.crs)

    joined = gpd.sjoin(pts, counties[["countyfips", "state_usps", "geometry"]],
                       how="left", predicate="within")

    audit["multiple_polygon_matches"] = int(joined.index.duplicated(keep=False).sum())
    joined = joined[~joined.index.duplicated(keep="first")].copy()

    unmatched = joined["countyfips"].isna()
    audit["sites_unmatched_to_county"] = int(unmatched.sum())

    matched = joined[~unmatched].copy()
    matched["state_agrees"] = (
        matched["state"].astype(str).str.strip().str.lower()
        == matched["state_usps"].map(USPS_TO_NAME).astype(str).str.lower())
    audit["state_mismatch_after_join"] = int((~matched["state_agrees"]).sum())

    drop = ["geometry", "index_right"]
    review = pd.concat([
        sites[sites["lat"].isna()].assign(review_reason="missing coordinates"),
        joined[unmatched].drop(columns=drop, errors="ignore")
                        .assign(review_reason="point outside all in-scope county polygons"),
        matched[~matched["state_agrees"]].drop(columns=drop, errors="ignore")
                        .assign(review_reason="registry state disagrees with assigned county state"),
    ], ignore_index=True)

    return matched.drop(columns=drop, errors="ignore"), review


# ---------------------------------------------------------------------------
# 6-7. Aggregate, join, engineer
# ---------------------------------------------------------------------------
def aggregate(matched: pd.DataFrame) -> pd.DataFrame:
    def counts(mask: pd.Series, suffix: str) -> pd.DataFrame:
        sub = matched[mask]
        return sub.groupby("countyfips").agg(
            **{f"trial_site_pairs_{suffix}": ("nct_id", "size"),
               f"trials_{suffix}": ("nct_id", "nunique"),
               f"facilities_{suffix}": ("facility_key", "nunique")})

    out = counts(matched["is_recruiting_site"], "recruiting").join(
        counts(matched["is_active_site"], "active"), how="outer")
    return out.fillna(0).astype(int)


def build(places: pd.DataFrame, agg: pd.DataFrame) -> pd.DataFrame:
    df = places.merge(agg, on="countyfips", how="left")
    assert len(df) == len(places), "join expanded rows"
    assert df["countyfips"].is_unique, "duplicate counties after join"

    count_cols = [c for c in df.columns
                  if c.startswith(("trial_site_pairs_", "trials_", "facilities_"))]
    df[count_cols] = df[count_cols].fillna(0).astype(int)

    for cohort in ("recruiting", "active"):
        df[f"has_site_{cohort}"] = df[f"trial_site_pairs_{cohort}"] > 0
        pop = df["totalpopulation"].where(df["totalpopulation"] > 0)
        adult = df["totalpop18plus"].where(df["totalpop18plus"] > 0)
        df[f"sites_per_100k_{cohort}"] = 100_000 * df[f"trial_site_pairs_{cohort}"] / pop
        df[f"sites_per_100k_adults_{cohort}"] = 100_000 * df[f"trial_site_pairs_{cohort}"] / adult

    # Potential trial desert: prevalence strictly above the unweighted median of
    # eligible counties with a non-missing estimate, AND zero qualifying sites.
    # Counties with no estimate keep a MISSING flag, never False.
    eligible = df["stroke_crudeprev"].notna()
    adj_ok = df["stroke_adjprev"].notna()
    median_crude = df.loc[eligible, "stroke_crudeprev"].median()
    median_adj = df.loc[adj_ok, "stroke_adjprev"].median()
    audit["median_crude_prevalence"] = float(median_crude)
    audit["median_adjusted_prevalence"] = float(median_adj)

    for cohort in ("recruiting", "active"):
        flag = pd.Series(pd.NA, index=df.index, dtype="boolean")
        flag[eligible] = ((df.loc[eligible, "stroke_crudeprev"] > median_crude)
                          & (~df.loc[eligible, f"has_site_{cohort}"]))
        df[f"potential_desert_{cohort}"] = flag

    flag = pd.Series(pd.NA, index=df.index, dtype="boolean")
    flag[adj_ok] = ((df.loc[adj_ok, "stroke_adjprev"] > median_adj)
                    & (~df.loc[adj_ok, "has_site_active"]))
    df["potential_desert_active_ageadj"] = flag

    df["burden_quintile"] = pd.qcut(df["stroke_crudeprev"], 5, labels=[1, 2, 3, 4, 5])
    df["population_quintile"] = pd.qcut(df["totalpopulation"], 5, labels=[1, 2, 3, 4, 5])

    numeric = df.select_dtypes(include=[np.number]).to_numpy(dtype=float, na_value=0.0)
    assert not np.isinf(numeric).any(), "infinite feature produced"
    assert (df[count_cols] >= 0).all().all(), "negative count produced"
    return df


# ---------------------------------------------------------------------------
# Confounding check: does burden predict access within population strata?
# ---------------------------------------------------------------------------
def population_stratified(df: pd.DataFrame) -> pd.DataFrame:
    sub = df[df["stroke_crudeprev"].notna() & df["population_quintile"].notna()]
    rows = []
    for q, grp in sub.groupby("population_quintile", observed=True):
        med = grp["stroke_crudeprev"].median()
        low = grp[grp["stroke_crudeprev"] <= med]
        high = grp[grp["stroke_crudeprev"] > med]
        rows.append({
            "population_quintile": int(q),
            "counties": len(grp),
            "median_population": int(grp["totalpopulation"].median()),
            "pct_with_site_low_burden": round(100 * low["has_site_active"].mean(), 1),
            "pct_with_site_high_burden": round(100 * high["has_site_active"].mean(), 1),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Quality report
# ---------------------------------------------------------------------------
def write_report(df: pd.DataFrame, review: pd.DataFrame, strat: pd.DataFrame) -> None:
    lines = [
        "# Processing quality report",
        "",
        "Generated by `scripts/03_clean_merge.py` from the committed snapshots in",
        "`data/raw/`. Raw inputs were read only.",
        "",
        "## Coverage",
        "",
        f"- PLACES counties: **{audit['places_counties']:,}**, one row per county in the output.",
        f"- Counties with no stroke estimate: **{audit['places_missing_prevalence']:,}** "
        f"(`{audit['places_missing_states']}`). These keep a MISSING desert flag, are",
        "  excluded from the median, and must render as \"no estimate\" on prevalence maps,",
        "  never as low-burden areas.",
        f"- Studies in snapshot: **{audit['studies_in_snapshot']:,}**; US location rows: "
        f"**{audit['location_rows_us']:,}** of {audit['location_rows_all_countries']:,} "
        "across all countries.",
        "",
        "## Site status coverage",
        "",
        f"- Site status missing on **{audit['site_status_missing']:,}** US location rows. "
        "Missing status is reported as unknown, never inferred as recruiting.",
        f"- Status breakdown: `{audit['site_status_counts']}`",
        f"- Qualifying trial/site pairs, strict recruiting cohort: **{audit['recruiting_pairs']:,}**",
        f"- Qualifying trial/site pairs, broader active cohort: **{audit['active_pairs']:,}**",
        "",
        "  The strict cohort is small largely because status is so often absent. A",
        "  zero-site count under the strict definition therefore reflects unknown",
        "  coverage as much as absent infrastructure, so the active cohort is the safer",
        "  basis for any public claim. Both are retained for sensitivity comparison.",
        "",
        "## Cohort and deduplication",
        "",
        f"- Excluded as non-cerebrovascular by explicit condition string "
        f"({', '.join(NON_CEREBROVASCULAR)}): `{audit['excluded_condition_nct_ids']}`",
        f"- Duplicate trial/site pairs removed: **{audit['duplicate_pairs_removed']:,}** "
        "(keyed on study + normalized facility + city + state, never on coordinates).",
        f"- Blank facility names requiring review: **{audit['blank_facility_names']:,}**",
        f"- Distinct trial/site pairs retained: **{audit['trial_site_pairs']:,}**",
        "",
        "## Spatial assignment",
        "",
        f"- Boundary polygons in scope: **{audit['boundary_polygons_in_scope']:,}** of "
        f"{audit['boundary_polygons_all']:,} (territories excluded).",
        f"- Location rows with no coordinates: **{audit['coords_missing']:,}**",
        f"- Points matching multiple polygons: **{audit['multiple_polygon_matches']:,}**",
        f"- Points inside no in-scope polygon: **{audit['sites_unmatched_to_county']:,}**",
        f"- Registry state disagreeing with assigned county state: "
        f"**{audit['state_mismatch_after_join']:,}**",
        f"- Rows written to `data/processed/site_assignment_review.csv`: **{len(review):,}**. "
        "No site was moved to a nearest county.",
        "- Connecticut: PLACES and the 2023 boundary file both use the nine planning",
        "  region equivalents, so the county vintages are compatible.",
        "",
        "## Reconciliation",
        "",
        f"- Assigned active trial/site pairs summed across counties: "
        f"**{int(df['trial_site_pairs_active'].sum()):,}**",
        f"- Median crude prevalence (eligible counties): "
        f"**{audit['median_crude_prevalence']:.2f}%**",
        f"- Median age-adjusted prevalence: **{audit['median_adjusted_prevalence']:.2f}%**",
        "",
        "## Confounding: population size",
        "",
        "Trial sites sit at academic medical centres, which sit in populous counties.",
        "Before reading any burden/access association as evidence about siting, compare",
        "counties of similar size. Within each population quintile, the share of counties",
        "hosting an active site, split at that stratum's own median stroke prevalence:",
        "",
        strat.to_markdown(index=False),
        "",
        "Where the two right-hand columns are close within a stratum, the unadjusted",
        "association is largely a population-size artifact rather than evidence that",
        "trials avoid high-burden places. Report the adjusted comparison alongside any",
        "unadjusted figure.",
        "",
        "## Unresolved limitations",
        "",
        "- Zero sites means no qualifying **observed assigned** site, not absence of access.",
        "- A registry `geoPoint` can locate a city centroid rather than a hospital address.",
        "- County presence omits cross-border travel, referral patterns, transport,",
        "  insurance, eligibility and site capacity.",
        "- ClinicalTrials.gov records participant origin only by country, so whether",
        "  patients travel in from surrounding counties is not observable in this data.",
        "- PLACES 2023 estimates and a live registry snapshot cover different periods.",
        "- The 2025 PLACES release omits stroke estimates for all of KY and PA; the 2024",
        "  release (`d3i6-k6z5`) covers them. Switching releases is a team decision and is",
        "  not made here.",
        "",
    ]
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "processing_quality_report.md").write_text("\n".join(lines))


def main() -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    places = load_places()
    sites = load_sites()
    counties = load_counties()
    matched, review = assign_counties(sites, counties)
    df = build(places, aggregate(matched))
    strat = population_stratified(df)

    matched.to_csv(PROCESSED / "trial_sites_clean.csv", index=False)
    review.to_csv(PROCESSED / "site_assignment_review.csv", index=False)
    df.to_csv(PROCESSED / "county_analysis.csv", index=False)
    strat.to_csv(PROCESSED / "population_stratified_check.csv", index=False)

    state = (df.groupby("stateabbr")
               .agg(counties=("countyfips", "size"),
                    sites_active=("trial_site_pairs_active", "sum"),
                    population=("totalpopulation", "sum"),
                    mean_crude_prev=("stroke_crudeprev", "mean"),
                    desert_counties=("potential_desert_active", "sum"))
               .assign(sites_per_100k=lambda d: 100_000 * d.sites_active / d.population)
               .sort_values("sites_per_100k"))
    state.to_csv(PROCESSED / "state_summary.csv")
    write_report(df, review, strat)

    print(f"counties written            {len(df):,}")
    print(f"trial/site pairs assigned   {len(matched):,}")
    print(f"rows needing review         {len(review):,}")
    print(f"counties with an active site{int(df.has_site_active.sum()):>6,}")
    print(f"potential deserts (active)  {int(df.potential_desert_active.sum()):,}")
    print("\nsee reports/processing_quality_report.md")


if __name__ == "__main__":
    main()
