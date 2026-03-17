# State Files

These JSON files track the known state of each monitored geofeed between runs.
They are updated automatically by the GitHub Actions workflow after each run.

**Do not modify or overwrite these files in manual commits.**
Doing so can cause alert deduplication issues — alerts may re-fire for changes
that were already seen and alerted on in a previous run.
