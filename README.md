# AWS Geofeed Monitor

Monitors the accuracy of the [AWS IP geofeed](https://ip-ranges.amazonaws.com/geo-ip-feed.csv) by validating geolocation claims against third-party geolocation databases.

## What it does

1. Fetches the AWS geofeed CSV — a list of IP prefixes with their claimed country, subdivision, and city.
2. Looks up each prefix in multiple geolocation providers (MaxMind GeoLite2, IPinfo Lite, IP2Location Lite) and compares the results.
3. Generates a self-contained HTML report with:
   - Global accuracy statistics (by prefix and by address count)
   - Per-location breakdown with expandable prefix details
   - Search by prefix or IP address
   - Filter to show only inaccurate entries

## Live Report

The report is published via GitHub Pages and refreshed daily:

**https://chriselsen.github.io/AWS-Geofeed-Monitor/**

## Running locally

```bash
pip install -r requirements.txt

export MAXMIND_ACCOUNT_ID="<your_account_id>"
export MAXMIND_LICENSE_KEY="<your_license_key>"
export IPINFO_TOKEN="<your_token>"
export IP2LOCATION_TOKEN="<your_token>"

python monitor-geofeed.py
```

The report is written to `index.html`.

## Providers

| Provider | Database | Coverage |
|----------|----------|----------|
| [MaxMind](https://www.maxmind.com/) | GeoLite2-City | Country + City |
| [IPinfo](https://ipinfo.io/) | IPinfo Lite | Country only |
| [IP2Location](https://www.ip2location.com/) | DB3 Lite | Country + City |

## License

This project is for monitoring purposes. The geolocation databases are subject to their respective licenses.
