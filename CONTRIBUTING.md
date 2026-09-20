# Working together

Each group member needs at least one substantive pull request. The requested
bootstrap push to `main` does not substitute for those individual PRs.

1. Pull the current `main` and create a descriptive feature branch.
2. Keep acquisition, processing, and EDA changes focused so they are reviewable.
3. Never clean data in `data/raw/`. Save derived outputs in `data/processed/`.
4. Run `python scripts/validate_data.py` and
   `python -m unittest discover -s tests -v`, plus checks relevant to the change.
5. Commit code, output data, and documentation needed to reproduce your change.
   Exclude virtual environments, credentials, and personal files.
6. Push your branch, open a PR to `main`, and request your partner's review.
7. Discuss cohort definitions and unresolved data issues before merging. Record
   decisions in the handoff/field guide so the visualization work stays aligned.

Raw data are small enough for ordinary Git. Commit intended cleaned CSVs and
final figures; do not add broad ignore rules for `data/` or `figures/`. Refresh
upstream data only intentionally, one downloader at a time, and include the
updated manifest. Do not present a snapshot inventory as final EDA findings.
