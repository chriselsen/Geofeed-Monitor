"""Load and group RFC 8805 geofeed CSVs."""

import csv
import io
import re
from collections import defaultdict
from urllib.request import urlopen


def _resolve_microsoft_url(page_url):
    """Scrape the Microsoft download page to get the current direct CSV URL."""
    html = urlopen(page_url).read().decode("utf-8")
    m = re.search(r'https://download\.microsoft\.com/download/[^"]+geoloc-Microsoft\.csv', html)
    if not m:
        raise RuntimeError("Could not find geoloc-Microsoft.csv URL on Microsoft download page")
    return m.group(0)


def load_geofeed(url, fmt="rfc8805"):
    """Load a geofeed CSV. Returns dict: prefix_str -> (country, subdiv, city)."""
    if fmt == "microsoft":
        url = _resolve_microsoft_url(url)
    print(f"Loading geofeed from {url}...")
    data = urlopen(url).read().decode("utf-8")
    geofeed = {}
    for row in csv.reader(io.StringIO(data)):
        if not row or row[0].startswith("#"):
            continue
        if fmt == "microsoft":
            # Header: IP Range,Country,Region,City,Postal Code
            if row[0].strip() == "IP Range":
                continue
            prefix = row[0].strip()
            country = row[1].strip() if len(row) > 1 else ""
            subdiv = row[2].strip() if len(row) > 2 else ""
            city = row[3].strip().title() if len(row) > 3 else ""
        else:
            prefix = row[0].strip()
            country = row[1].strip() if len(row) > 1 else ""
            subdiv = row[2].strip() if len(row) > 2 else ""
            city = row[3].strip() if len(row) > 3 else ""
        geofeed[prefix] = (country, subdiv, city)
    print(f"  Loaded {len(geofeed)} geofeed entries")
    return geofeed


def group_by_location(geofeed):
    """Group geofeed prefixes by (city, country). Returns sorted list of (country_code, display_name, prefixes)."""
    groups = defaultdict(list)
    for prefix, (country, subdiv, city) in geofeed.items():
        key = (city or country, country)
        groups[key].append((prefix, country, subdiv, city))

    sorted_locations = []
    for key in sorted(groups):
        city_name, country_code = key
        display = f"{city_name}, {country_code}" if city_name != country_code else country_code
        sorted_locations.append((country_code, display, groups[key]))
    return sorted_locations
