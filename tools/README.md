# Tools

Utility scripts for managing geofeed-related RIR records.

---

## arin-add-geofeed.py

Adds, updates, or removes RFC 9092 `Geofeed` remarks on ARIN network records for a given organization.

### What it does

1. Fetches all ARIN net handles registered to an org via RDAP
2. For each net record, checks whether a `Geofeed` remark already exists in the comments field
3. If no remark exists — adds `Geofeed <url>` as a new comment line
4. If a remark exists with a different URL — updates it (requires `--update` flag)
5. If a remark already matches the target URL — skips it
6. With `--remove` — removes any existing `Geofeed` remark regardless of URL
7. With `--root-only` — only processes the root allocation (the record whose parent net is not owned by the same org), skipping all sub-allocations

By default operates against the **ARIN OT&E (test) environment** (`reg.ote.arin.net`). Pass `--prod` to target production.

### Requirements

- Python 3.6+, no external dependencies (stdlib only)
- An ARIN API key set via the `ARIN_API_KEY` environment variable
- For OT&E: a separate API key generated at `https://www.ote.arin.net` → Settings → Manage API Keys

### Usage

```bash
# Always dry-run first to preview changes
ARIN_API_KEY=<key> python3 arin-add-geofeed.py \
    --org <org-handle> \
    --geofeed <geofeed-url> \
    --dry-run

# Add geofeed remark to all records that don't have one (OT&E)
ARIN_API_KEY=<ote-key> python3 arin-add-geofeed.py \
    --org <org-handle> \
    --geofeed <geofeed-url>

# Add only to the root allocation, skip sub-allocations (OT&E)
ARIN_API_KEY=<ote-key> python3 arin-add-geofeed.py \
    --org <org-handle> \
    --geofeed <geofeed-url> \
    --root-only

# Update records that have a different (stale) geofeed URL (OT&E)
ARIN_API_KEY=<ote-key> python3 arin-add-geofeed.py \
    --org <org-handle> \
    --geofeed <geofeed-url> \
    --update

# Remove all Geofeed remarks (OT&E)
ARIN_API_KEY=<ote-key> python3 arin-add-geofeed.py \
    --org <org-handle> \
    --remove

# Apply to production (will prompt for confirmation)
ARIN_API_KEY=<prod-key> python3 arin-add-geofeed.py \
    --org <org-handle> \
    --geofeed <geofeed-url> \
    --root-only \
    --prod
```

### Arguments

| Argument | Description |
|----------|-------------|
| `--org` | ARIN org handle (e.g. `AL-3043`) — required |
| `--geofeed` | Geofeed URL to register (e.g. `https://geofeed.example.com/geofeed.txt`) — required unless `--remove` |
| `--update` | Replace existing Geofeed remarks that point to a different URL, normalise non-standard formats (e.g. colon variant), and deduplicate multiple Geofeed lines into one canonical entry |
| `--root-only` | Only process the root allocation (parent net not owned by same org); skip sub-allocations |
| `--remove` | Remove all Geofeed remarks regardless of URL (mutually exclusive with `--geofeed` and `--update`) |
| `--dry-run` | Preview changes without modifying any records |
| `--prod` | Target production (`reg.arin.net`) instead of OT&E (`reg.ote.arin.net`) |

### Example: add to root only

```
Environment : PRODUCTION
Org handle  : AL-3043
Geofeed URL : https://geofeed.as213151.net/geofeed.txt
Mode        : add
Root only   : True
Dry run     : False

Fetching net handles for org AL-3043...
  Found 9 net records

  NET6-2602-FB2A-1 ... (root) UPDATED
  NET6-2602-FB2A-C0-1 ... SKIP (sub-allocation, not root)
  NET6-2602-FB2A-C0-2 ... SKIP (sub-allocation, not root)
  NET6-2602-FB2A-C4-1 ... SKIP (sub-allocation, not root)
  ...

Results: 1 updated, 8 skipped, 0 errors
```

### Example: remove all

```
Environment : PRODUCTION
Org handle  : AL-3043
Mode        : remove
Root only   : False
Dry run     : False

Fetching net handles for org AL-3043...
  Found 9 net records

  NET6-2602-FB2A-1 ... REMOVED (Geofeed https://geofeed.as213151.net/geofeed.txt)
  NET6-2602-FB2A-C0-1 ... REMOVED (Geofeed https://geofeed.as213151.net/geofeed.txt)
  ...

Results: 9 removed, 0 skipped, 0 errors
```

### Notes

- The script only modifies the `comment` field of net records. All other fields (netBlocks, orgHandle, pocLinks, etc.) are preserved exactly as-is.
- Existing comment lines (e.g. certificates, NOC info) are preserved when adding a new Geofeed line.
- RFC 9092/9632 specifies exactly one Geofeed remark per record. `--update` enforces this by removing all existing Geofeed lines before inserting a single canonical one.
- `--root-only` determines the root by fetching the parent net record and checking its org handle. A record is considered root if its parent net belongs to a different org (e.g. ARIN itself). For orgs that received a delegation from another org, the delegated block is treated as the root relative to that org.
- The OT&E environment is refreshed monthly (first Monday of each month) from production. Changes made in OT&E are wiped on the next refresh.
- This script handles ARIN-registered prefixes only. For RIPE, APNIC, LACNIC, or AFRINIC prefixes, each RIR has its own API.

---

## ripe-add-geofeed.py *(planned)*

A RIPE equivalent of `arin-add-geofeed.py` is planned. Key differences from the ARIN script:

- **API:** RIPE REST API (`https://rest.db.ripe.net`) with NRTM/password or API key authentication
- **Object types:** `inetnum` (IPv4) and `inet6num` (IPv6)
- **Two fields to manage** — RIPE supports both:
  - `remarks: Geofeed https://...` — the RFC 9092 remarks-based approach (backward compatible, recognised by all tools)
  - `geofeed: https://...` — a dedicated RIPE attribute introduced to support RFC 9632 natively (preferred going forward)
- **Test environment:** RIPE provides a test database at `https://rest-test.db.ripe.net` (equivalent to ARIN OT&E)
- **Authentication:** RIPE uses maintainer (`mnt-by`) objects with password or SSO credentials, not API keys
- **`--root-only`:** RIPE's object hierarchy uses `parent` attributes; root detection logic will differ slightly from ARIN
