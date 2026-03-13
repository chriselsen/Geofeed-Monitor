# Geofeed Monitor

Monitors the accuracy of [RFC 8805 geofeeds](https://datatracker.ietf.org/doc/html/rfc8805) by validating geolocation claims against third-party geolocation databases.

## What it does

1. Fetches geofeed CSVs — lists of IP prefixes with their claimed country, subdivision, and city.
2. Looks up each prefix in multiple geolocation providers (MaxMind GeoLite2, IPinfo Lite, IP2Location Lite) and compares the results.
3. Generates self-contained HTML reports with:
   - Global accuracy statistics (by prefix and by address count)
   - Per-location breakdown with expandable prefix details
   - Search by prefix or IP address
   - Filter to show only inaccurate entries

## Monitored Geofeeds

| Network | Geofeed | Report |
|---------|---------|--------|
| [AWS](https://aws.amazon.com/) | [geo-ip-feed.csv](https://ip-ranges.amazonaws.com/geo-ip-feed.csv) | [aws.html](https://chriselsen.github.io/Geofeed-Monitor/aws.html) |
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

python monitor-geofeed.py
```

The reports are written to `aws.html`, `as213151.html`, and a landing page `index.html`.

## Providers

| Provider | Database | Coverage |
|----------|----------|----------|
| [MaxMind](https://www.maxmind.com/) | GeoLite2-City | Country + City |
| [IPinfo](https://ipinfo.io/) | IPinfo Lite | Country only |
| [IP2Location](https://www.ip2location.com/) | DB3 Lite | Country + City |

## License

This project is for monitoring purposes. The geolocation databases are subject to their respective licenses.
