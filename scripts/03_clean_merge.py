"""Partner-owned processing entry point. See docs/PROCESSING_HANDOFF.md."""


def main():
    # 1. Read countyfips as a string and retain both prevalence measures and CIs.
    # 2. Flatten study locations, retain U.S. sites, audit missing fields/statuses.
    # 3. Deduplicate trial/site pairs; distinguish these from unique facilities.
    # 4. Assign counties with a CRS-aware spatial join; audit unmatched points.
    # 5. Aggregate recruiting sites and broader active trial infrastructure separately.
    # 6. Left join onto ALL PLACES counties; distinguish missing data from zero sites.
    # 7. Engineer per-capita rates and a reviewed potential-desert definition.
    # 8. Write documented outputs and a quality report, then validate the joins.
    raise SystemExit(
        "Processing is not implemented yet. Start with docs/PROCESSING_HANDOFF.md; "
        "the required source snapshots are available in data/raw/."
    )


if __name__ == "__main__":
    main()
