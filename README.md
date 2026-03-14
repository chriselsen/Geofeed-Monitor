# Geofeed Monitor

Monitors the accuracy of [RFC 8805 geofeeds](https://datatracker.ietf.org/doc/html/rfc8805) by validating geolocation claims against third-party geolocation databases, routing tables, and the UN/LOCODE location registry.

## What it does

1. Fetches geofeed CSVs — lists of IP prefixes with their claimed country, subdivision, and city.
2. Looks up each prefix in multiple geolocation providers (MaxMind GeoLite2, IPinfo Lite, IP2Location Lite) and compares the results.
3. Validates each location entry against the [UN/LOCODE](https://service.unece.org/trade/locode/) registry — checking that the city exists, belongs to the claimed country, and is in the correct subdivision.
4. Checks each prefix for visibility in the global routing table using [RIPE RIS](https://www.ripe.net/analyse/internet-measurements/routing-information-service-ris) whois dumps.
5. Generates self-contained HTML reports with:
   - Global accuracy statistics (by prefix and by address count)
   - Per-location breakdown with expandable prefix details
   - UN/LOCODE validation warnings per location
   - Routing visibility indicators per prefix (visible / not visible / too specific)
   - Search by prefix or IP address
   - Filter to show only inaccurate entries
6. Sends Slack alerts on detected changes or issues (see [Alerting](#alerting)).

## Monitored Geofeeds

| Network | Geofeed | Report |
|---------|---------|--------|
| [AWS](https://aws.amazon.com/) (Official) | [geo-ip-feed.csv](https://ip-ranges.amazonaws.com/geo-ip-feed.csv) | [aws.html](https://chriselsen.github.io/Geofeed-Monitor/aws.html) |
| [Google Cloud](https://cloud.google.com/) | [cloud_geofeed](https://www.gstatic.com/ipranges/cloud_geofeed) | [gcp.html](https://chriselsen.github.io/Geofeed-Monitor/gcp.html) |
| [Microsoft](https://www.microsoft.com/) | [geoloc-Microsoft.csv](https://www.microsoft.com/en-us/download/details.aspx?id=53601) | [microsoft.html](https://chriselsen.github.io/Geofeed-Monitor/microsoft.html) |
| [AWS](https://aws.amazon.com/) (Christian Elsen) | [aws-geofeed.txt](https://raw.githubusercontent.com/chriselsen/AWS-Geofeed/main/data/aws-geofeed.txt) | [aws-ce.html](https://chriselsen.github.io/Geofeed-Monitor/aws-ce.html) |
| [AS213151](https://as213151.net/) | [as213151-geo-ip.txt](https://raw.githubusercontent.com/AS213151/rfc8805-geofeed/main/as213151-geo-ip.txt) | [as213151.html](https://chriselsen.github.io/Geofeed-Monitor/as213151.html) |
| [Starlink](https://www.starlink.com/) | [geoip.starlinkisp.net](https://geoip.starlinkisp.net/) | [starlink.html](https://chriselsen.github.io/Geofeed-Monitor/starlink.html) |

## Live Report

The reports are published via GitHub Pages and refreshed daily:

**https://chriselsen.github.io/Geofeed-Monitor/**

## Running locally

```bash
pip install -r requirements.txt

export MAXMIND_ACCOUNT_ID="<your_account_id>"
export MAXMIND_LICENSE_KEY="<your_license_key>"
export IPINFO_TOKEN="<your_token>"
export IP2LOCATION_TOKEN="<your_token>"

python3 monitor-geofeed.py
```

Provider credentials are optional — if unset, that provider is skipped. Reports are written to `aws.html`, `gcp.html`, `microsoft.html`, `aws-ce.html`, `as213151.html`, `starlink.html`, and a landing page `index.html`.

## Providers

| Provider | Database | Coverage |
|----------|----------|----------|
| [MaxMind](https://www.maxmind.com/) | GeoLite2-City | Country + City |
| [IPinfo](https://ipinfo.io/) | IPinfo Lite | Country only |
| [IP2Location](https://www.ip2location.com/) | DB3 Lite | Country + City |

## Validation

### UN/LOCODE

Each geofeed location entry is validated against the official [UN/LOCODE 2024-2](https://service.unece.org/trade/locode/loc242csv.zip) dataset. The following issues are flagged with a warning icon on the location row:

- City name not found anywhere in UN/LOCODE
- City found but not in the claimed country (e.g. Hong Kong claimed as `CN` instead of `HK`)
- City found in the correct country but wrong subdivision (e.g. Frankfurt am Main in `DE-RP` instead of `DE-HE`)

City name matching is diacritic- and case-insensitive, and handles parenthetical alternate names (e.g. `Helsinki (Helsingfors)` matches `Helsinki`) and alias entries (e.g. `Copenhagen = København` matches `Copenhagen`).

### Routing Visibility

Each prefix is checked against [RIPE RIS](https://www.ris.ripe.net/dumps/) whois dumps (updated every ~5 minutes), requiring visibility by at least 2 peers. A prefix is considered routed if:

- The exact prefix is announced, **or**
- A covering supernet is announced (e.g. geofeed has `/24`, BGP has `/23`), **or**
- A more-specific is announced (e.g. geofeed has `/23`, BGP has `/24`)

Prefixes more specific than `/24` (IPv4) or `/48` (IPv6) are marked as too specific to appear in the global routing table and shown with a grey indicator.

## Alerting

Slack alerts are sent via webhooks on a per-feed, per-alert-type basis. Each alert type has a fixed JSON schema for use with Slack Workflows.

### Alert types

| Type | Trigger | Key fields |
|------|---------|------------|
| `UNREACHABLE` | Feed URL failed to load | `feed`, `url` |
| `EMBARGO` | Location claims a sanctioned country | `feed`, `location`, `country`, `prefix_count`, `prefixes` |
| `NEW_LOCATION` | A new location group appeared | `feed`, `location`, `country`, `prefix_count`, `prefixes` |
| `REMOVED_LOCATION` | A previously known location is gone | `feed`, `location`, `country`, `prefix_count`, `prefixes` |
| `NEW_PREFIX` | Prefixes added to an existing location | `feed`, `location`, `country`, `prefix_count`, `prefixes` |
| `REMOVED_PREFIX` | Prefixes removed from an existing location | `feed`, `location`, `country`, `prefix_count`, `prefixes` |
| `ACCURACY_DROP` | Country or city accuracy dropped ≥5pp or fell below 80% | `feed`, `location`, `metric`, `previous_pct`, `current_pct`, `drop_pp` |
| `UNROUTED` | A previously routed prefix is no longer visible | `feed`, `prefix`, `proto` |
| `LOCODE` | A new UN/LOCODE violation was introduced | `feed`, `prefix`, `location`, `issue` |

### Webhook configuration

Webhooks are resolved per feed and alert type with a fallback chain:

```
SLACK_WEBHOOK_<FEED>_<TYPE>  →  SLACK_WEBHOOK_<TYPE>
```

Where `<FEED>` is the feed's output filename uppercased (e.g. `AWS`, `GCP`, `MICROSOFT`, `STARLINK`) and `<TYPE>` is one of the alert types above.

Example — AWS embargo alerts with global fallback:
```
SLACK_WEBHOOK_AWS_EMBARGO   (feed-specific)
SLACK_WEBHOOK_EMBARGO       (global fallback)
```

Sanctioned countries default to the OFAC comprehensive list: `IR`, `CU`, `KP`, `SY`. This can be overridden per feed via the `embargo_countries` config key.

### State

Alert state is stored in `state/<feed>.json` and committed to the repository by the GitHub Action after each run. This tracks known locations, prefixes, routing status, and LOCODE issues to detect changes between runs.

## License

This project is for monitoring purposes. The geolocation databases are subject to their respective licenses.
