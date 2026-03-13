#!/usr/bin/env python3

"""Monitor AWS Geofeed against geolocation databases and generate an HTML report."""

import base64
import csv
import io
import ipaddress
import os
import subprocess
import tarfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

import maxminddb
import IP2Location
import zipfile

DATA_DIR = Path("./data")

MAXMIND_DOWNLOAD_URL = "https://download.maxmind.com/geoip/databases/GeoLite2-City/download?suffix=tar.gz"
MAXMIND_DIR = DATA_DIR / "maxmind"
MAXMIND_DB_FILE = MAXMIND_DIR / "GeoLite2-City.mmdb"

IPINFO_DOWNLOAD_URL = "https://ipinfo.io/data/ipinfo_lite.mmdb"
IPINFO_DIR = DATA_DIR / "ipinfo"
IPINFO_DB_FILE = IPINFO_DIR / "ipinfo_lite.mmdb"

ASSETS_DIR = DATA_DIR / "assets"
AWS_LOGO_FILE = ASSETS_DIR / "aws-logo.svg"
AWS_LOGO_URL = "https://docs.aws.amazon.com/assets/r/images/aws_logo_dark.svg"
AWS_CARD_LOGO_FILE = ASSETS_DIR / "aws-card-logo.svg"
AWS_CARD_LOGO_URL = "https://upload.wikimedia.org/wikipedia/commons/9/93/Amazon_Web_Services_Logo.svg"
AS213151_LOGO_FILE = ASSETS_DIR / "as213151-logo.png"
AS213151_LOGO_URL = "https://as213151.net/images/AS213151.png"
STARLINK_LOGO_FILE = ASSETS_DIR / "starlink-logo.svg"
STARLINK_LOGO_URL = "https://upload.wikimedia.org/wikipedia/commons/a/a8/Starlink_Logo.svg"

MAXMIND_FAVICON_FILE = ASSETS_DIR / "maxmind-favicon.ico"
MAXMIND_FAVICON_URL = "https://www.maxmind.com/favicon.ico"
IPINFO_FAVICON_FILE = ASSETS_DIR / "ipinfo-favicon.ico"
IPINFO_FAVICON_URL = "https://ipinfo.io/favicon.ico"

IP2LOCATION_DOWNLOAD_URL_V6 = "https://www.ip2location.com/download/"
IP2LOCATION_DIR = DATA_DIR / "ip2location"
IP2LOCATION_DB_FILE = IP2LOCATION_DIR / "IP2LOCATION-LITE-DB3.IPV6.BIN"
IP2LOCATION_FAVICON_FILE = ASSETS_DIR / "ip2location-favicon.ico"
IP2LOCATION_FAVICON_URL = "https://www.ip2location.com/favicon.ico"


# --- Database updaters ---


def update_maxmind():
    """Download and extract the latest GeoLite2-City mmdb database."""
    account_id = os.environ.get("MAXMIND_ACCOUNT_ID")
    license_key = os.environ.get("MAXMIND_LICENSE_KEY")
    if not account_id or not license_key:
        print("  MAXMIND_ACCOUNT_ID/MAXMIND_LICENSE_KEY not set, skipping update")
        return

    print("Downloading latest MaxMind GeoLite2-City...")
    MAXMIND_DIR.mkdir(parents=True, exist_ok=True)
    tar_path = MAXMIND_DIR / "GeoLite2-City.tar.gz"
    subprocess.run(
        ["curl", "-sS", "-L", "-o", str(tar_path),
         "-u", f"{account_id}:{license_key}",
         MAXMIND_DOWNLOAD_URL],
        check=True,
    )
    result = subprocess.run(["file", "--brief", str(tar_path)], capture_output=True, text=True)
    if "gzip" not in result.stdout.lower():
        print(f"  MaxMind download failed: {tar_path.read_text()[:120]}")
        tar_path.unlink()
        return

    with tarfile.open(tar_path, mode="r:gz") as tf:
        for member in tf.getmembers():
            if member.name.endswith(".mmdb"):
                with tf.extractfile(member) as src:
                    MAXMIND_DB_FILE.write_bytes(src.read())
                break
    tar_path.unlink()
    print("  MaxMind database updated")


GLOBE_SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M2 12h20"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>'
GLOBE_FAVICON = 'data:image/svg+xml,' + '<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22><rect width=%2224%22 height=%2224%22 rx=%224%22 fill=%22%23232f3e%22/><circle cx=%2212%22 cy=%2212%22 r=%228%22 fill=%22none%22 stroke=%22white%22 stroke-width=%221.2%22/><path d=%22M4 12h16%22 fill=%22none%22 stroke=%22white%22 stroke-width=%221.2%22/><path d=%22M12 4a12 12 0 0 1 3.2 8 12 12 0 0 1-3.2 8 12 12 0 0 1-3.2-8A12 12 0 0 1 12 4z%22 fill=%22none%22 stroke=%22white%22 stroke-width=%221.2%22/></svg>'

FEEDS = [
    {
        "url": "https://ip-ranges.amazonaws.com/geo-ip-feed.csv",
        "output": Path("./aws.html"),
        "title": "AWS Geofeed Monitoring Report (Official)",
        "topbar_title": "AWS Geofeed Monitoring Report (Official)",
        "logo_file": AWS_LOGO_FILE,
        "logo_type": "svg",
        "card_logo_file": AWS_CARD_LOGO_FILE,
        "card_logo_type": "svg",
    },
    {
        "url": "https://raw.githubusercontent.com/chriselsen/AWS-Geofeed/main/data/aws-geofeed.txt",
        "output": Path("./aws-ce.html"),
        "title": "AWS Geofeed Monitoring Report (Christian Elsen)",
        "topbar_title": "AWS Geofeed Monitoring Report (Christian Elsen)",
        "logo_file": AWS_LOGO_FILE,
        "logo_type": "svg",
        "card_logo_file": AWS_CARD_LOGO_FILE,
        "card_logo_type": "svg",
    },
    {
        "url": "https://raw.githubusercontent.com/AS213151/rfc8805-geofeed/main/as213151-geo-ip.txt",
        "output": Path("./as213151.html"),
        "title": "AS213151 Geofeed Monitoring Report",
        "topbar_title": "AS213151 Geofeed Monitoring Report",
        "logo_file": AS213151_LOGO_FILE,
        "logo_type": "png",
        "logo_invert": True,
        "card_logo_file": AS213151_LOGO_FILE,
        "card_logo_type": "png",
    },
    {
        "url": "https://geoip.starlinkisp.net/",
        "output": Path("./starlink.html"),
        "title": "Starlink Geofeed Monitoring Report",
        "topbar_title": "Starlink Geofeed Monitoring Report",
        "logo_file": STARLINK_LOGO_FILE,
        "logo_type": "svg",
        "logo_invert": True,
        "card_logo_file": STARLINK_LOGO_FILE,
        "card_logo_type": "svg",
    },
]


def download_assets():
    """Download static assets if not already present."""
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    for path, url in [
        (AWS_LOGO_FILE, AWS_LOGO_URL),
        (AWS_CARD_LOGO_FILE, AWS_CARD_LOGO_URL),
        (AS213151_LOGO_FILE, AS213151_LOGO_URL),
        (STARLINK_LOGO_FILE, STARLINK_LOGO_URL),
        (MAXMIND_FAVICON_FILE, MAXMIND_FAVICON_URL),
        (IPINFO_FAVICON_FILE, IPINFO_FAVICON_URL),
        (IP2LOCATION_FAVICON_FILE, IP2LOCATION_FAVICON_URL),
    ]:
        if path.exists():
            continue
        print(f"Downloading {path.name}...")
        subprocess.run(
            ["curl", "-sS", "-L", "-o", str(path), url],
            check=True,
        )


def update_ip2location():
    """Download the latest IP2Location Lite DB3 (IPv6) database."""
    token = os.environ.get("IP2LOCATION_TOKEN")
    if not token:
        print("  IP2LOCATION_TOKEN not set, skipping update")
        return

    print("Downloading latest IP2Location Lite DB3...")
    IP2LOCATION_DIR.mkdir(parents=True, exist_ok=True)
    tmp = IP2LOCATION_DIR / "db3.zip"
    subprocess.run(
        ["curl", "-sS", "-L", "-o", str(tmp),
         f"{IP2LOCATION_DOWNLOAD_URL_V6}?token={token}&file=DB3LITEBINIPV6"],
        check=True,
    )
    try:
        with zipfile.ZipFile(tmp) as zf:
            for name in zf.namelist():
                if name.endswith(".BIN"):
                    IP2LOCATION_DB_FILE.write_bytes(zf.read(name))
                    break
        tmp.unlink()
        print("  IP2Location database updated")
    except zipfile.BadZipFile:
        print(f"  IP2Location download failed: {tmp.read_text()[:120]}")
        tmp.unlink()


def update_ipinfo():
    """Download the latest IPinfo Lite mmdb database."""
    token = os.environ.get("IPINFO_TOKEN")
    if not token:
        print("  IPINFO_TOKEN not set, skipping update")
        return

    print("Downloading latest IPinfo Lite...")
    IPINFO_DIR.mkdir(parents=True, exist_ok=True)
    tmp = IPINFO_DIR / "ipinfo_lite.mmdb.tmp"
    subprocess.run(
        ["curl", "-sS", "-L", "-o", str(tmp),
         f"{IPINFO_DOWNLOAD_URL}?token={token}"],
        check=True,
    )
    result = subprocess.run(["file", "--brief", str(tmp)], capture_output=True, text=True)
    if "MaxMind" not in result.stdout and "data" not in result.stdout.lower():
        print(f"  IPinfo download failed: {tmp.read_text()[:120]}")
        tmp.unlink()
        return
    tmp.rename(IPINFO_DB_FILE)
    print("  IPinfo database updated")


# --- Lookups ---


def lookup_maxmind(ip_str, mm_reader):
    """Returns (country, city) or (None, None)."""
    result = mm_reader.get(ip_str)
    if not result:
        return (None, None)
    country = result.get("country", {}).get("iso_code")
    city = result.get("city", {}).get("names", {}).get("en")
    return (country, city)


def lookup_ip2location(ip_str, i2l_reader):
    """Returns (country, city) or (None, None)."""
    rec = i2l_reader.get_all(ip_str)
    if not rec:
        return (None, None)
    country = rec.country_short if rec.country_short not in ("-", "?") else None
    city = rec.city if rec.city not in ("-", "?") else None
    return (country, city)


def lookup_ipinfo(ip_str, ip_reader):
    """Returns (country, None) — IPinfo Lite has no city data."""
    result = ip_reader.get(ip_str)
    if not result:
        return (None, None)
    return (result.get("country_code"), None)


# --- Geofeed loader ---


def load_geofeed(url):
    """Load a geofeed CSV. Returns dict: prefix_str -> (country, subdiv, city)."""
    print(f"Loading geofeed from {url}...")
    data = urlopen(url).read().decode("utf-8")
    geofeed = {}
    for row in csv.reader(io.StringIO(data)):
        if not row or row[0].startswith("#"):
            continue
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


# --- Matching logic ---


def match_country(gf_country, provider_country):
    if not provider_country:
        return None
    return gf_country.strip().upper() == provider_country.strip().upper()


def match_city(gf_city, provider_city):
    if not provider_city:
        return None
    return gf_city.strip().lower() == provider_city.strip().lower()


# --- Main ---


def validate_prefixes(locations, mm_reader, ip_reader, i2l_reader):
    """Validate all prefixes against available providers. Returns results list."""
    results = []
    total = sum(len(entries) for _, _, entries in locations)
    done = 0
    for country_code, display_name, entries in locations:
        loc_results = []
        for prefix, gf_country, gf_subdiv, gf_city in entries:
            try:
                net = ipaddress.ip_network(prefix, strict=False)
            except ValueError:
                continue
            ip_str = str(net.network_address)

            mm_country, mm_city = lookup_maxmind(ip_str, mm_reader) if mm_reader else (None, None)
            ip_country, _ = lookup_ipinfo(ip_str, ip_reader) if ip_reader else (None, None)
            i2l_country, i2l_city = lookup_ip2location(ip_str, i2l_reader) if i2l_reader else (None, None)

            loc_results.append((
                prefix, net.version == 6, gf_country, gf_city,
                mm_country or "", mm_city or "",
                match_country(gf_country, mm_country), match_city(gf_city, mm_city),
                ip_country or "", match_country(gf_country, ip_country),
                i2l_country or "", i2l_city or "",
                match_country(gf_country, i2l_country), match_city(gf_city, i2l_city),
            ))
            done += 1
            if done % 500 == 0:
                print(f"  {done}/{total} prefixes validated...", end="\r")
        results.append((country_code, display_name, loc_results))
    print(f"  {done}/{total} prefixes validated.    ")
    return results


def generate_index(feeds):
    """Generate the landing page with links to each feed report."""
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    cards = []
    for feed in feeds:
        card_file = feed.get("card_logo_file", feed["logo_file"])
        card_type = feed.get("card_logo_type", feed["logo_type"])
        if card_file.exists():
            if card_type == "svg":
                logo_html = card_file.read_text(encoding="utf-8")
            else:
                b64 = base64.b64encode(card_file.read_bytes()).decode()
                logo_html = f'<img src="data:image/png;base64,{b64}" alt="">'
        else:
            logo_html = ""
        href = feed["output"].name
        cards.append(f'<a class="feed-card" href="{href}"><div class="feed-logo">{logo_html}</div>'
                     f'<div class="feed-title">{feed["title"]}</div></a>')

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Geofeed Monitor</title>
<link rel="icon" href="{GLOBE_FAVICON}">
<style>
  :root {{
    --squid-ink: #232f3e;
    --squid-ink-light: #37475a;
    --text-primary: #16191f;
    --text-secondary: #545b64;
    --bg-page: #f2f3f3;
    --bg-card: #ffffff;
    --border: #d5dbdb;
    --aws-orange: #ff9900;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: "Amazon Ember", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: var(--bg-page);
    color: var(--text-primary);
    line-height: 1.5;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }}
  .topbar {{
    background: var(--squid-ink);
    padding: 12px 32px;
    display: flex;
    align-items: center;
    gap: 16px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.15);
  }}
  .topbar svg {{ height: 40px; width: auto; }}
  .topbar h1 {{ color: #fff; font-size: 20px; font-weight: 700; }}
  .topbar .separator {{ width: 1px; height: 28px; background: var(--squid-ink-light); }}
  .container {{
    max-width: 900px;
    margin: 0 auto;
    padding: 48px 32px;
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 16px;
  }}
  .container h2 {{
    font-size: 22px;
    font-weight: 700;
    margin-bottom: 8px;
  }}
  .container p {{
    font-size: 14px;
    color: var(--text-secondary);
    margin-bottom: 24px;
    text-align: center;
    max-width: 600px;
  }}
  .feed-grid {{
    display: flex;
    gap: 24px;
    flex-wrap: wrap;
    justify-content: center;
  }}
  .feed-card {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 32px 40px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 16px;
    text-decoration: none;
    color: var(--text-primary);
    transition: box-shadow 0.2s, border-color 0.2s;
    width: 260px;
  }}
  .feed-card:hover {{
    border-color: var(--aws-orange);
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
  }}
  .feed-logo {{ height: 60px; display: flex; align-items: center; }}
  .feed-logo svg {{ height: 50px; }}
  .feed-logo img {{ height: 60px; }}
  .feed-title {{ font-size: 14px; font-weight: 600; text-align: center; }}
  footer {{ text-align: center; padding: 16px; font-size: 12px; color: #545b64; }}
</style>
</head>
<body>
<div class="topbar">
  {GLOBE_SVG}
  <div class="separator"></div>
  <h1>Geofeed Monitor</h1>
</div>
<div class="container">
  <h2>Select a Geofeed Report</h2>
  <p>Monitors the accuracy of RFC 8805 geofeeds by validating geolocation claims against third-party databases.</p>
  <div class="feed-grid">
    {''.join(cards)}
  </div>
</div>
<footer>Last updated: {now_utc}</footer>
</body></html>"""
    Path("./index.html").write_text(html, encoding="utf-8")
    print("Landing page written to index.html")


def main():
    update_maxmind()
    update_ipinfo()
    update_ip2location()
    download_assets()

    print("Loading databases...")
    mm_reader = maxminddb.open_database(str(MAXMIND_DB_FILE)) if MAXMIND_DB_FILE.exists() else None
    ip_reader = maxminddb.open_database(str(IPINFO_DB_FILE)) if IPINFO_DB_FILE.exists() else None
    i2l_reader = IP2Location.IP2Location(str(IP2LOCATION_DB_FILE)) if IP2LOCATION_DB_FILE.exists() else None
    if not mm_reader:
        print("  MaxMind database not available — skipping")
    if not ip_reader:
        print("  IPinfo database not available — skipping")
    if not i2l_reader:
        print("  IP2Location database not available — skipping")

    has_mm = mm_reader is not None
    has_ip = ip_reader is not None
    has_i2l = i2l_reader is not None

    for feed in FEEDS:
        print(f"\n=== {feed['title']} ===")
        geofeed = load_geofeed(feed["url"])
        locations = group_by_location(geofeed)
        print("Validating prefixes...")
        results = validate_prefixes(locations, mm_reader, ip_reader, i2l_reader)
        stats = compute_stats(results, has_mm, has_ip, has_i2l)
        print("Generating HTML report...")
        generate_html(results, stats, has_mm, has_ip, has_i2l, feed)
        print(f"Report written to {feed['output']}")

    if mm_reader:
        mm_reader.close()
    if ip_reader:
        ip_reader.close()
    if i2l_reader:
        i2l_reader.close()

    generate_index(FEEDS)


def compute_stats(results, has_mm=True, has_ip=True, has_i2l=True):
    """Compute global statistics from validation results."""
    total = v4 = v6 = v4_addrs = v6_addrs = 0
    country_all, country_v4, country_v6 = [], [], []
    city_all, city_v4, city_v6 = [], [], []
    w_country_all, w_country_v4, w_country_v6 = [], [], []
    w_city_all, w_city_v4, w_city_v6 = [], [], []
    # Per-provider match indices: (stat_key, result_tuple_index)
    provider_indices = []
    if has_mm:
        provider_indices += [("mm_c", 6), ("mm_ci", 7)]
    if has_ip:
        provider_indices += [("ip_c", 9)]
    if has_i2l:
        provider_indices += [("i2l_c", 12), ("i2l_ci", 13)]
    prov = {k: [] for k, _ in provider_indices}
    w_prov = {k: [] for k, _ in provider_indices}
    for _, _, loc_results in results:
        for r in loc_results:
            net = ipaddress.ip_network(r[0], strict=False)
            n = net.num_addresses
            total += 1
            country_matches = ([r[6]] if has_mm else []) + ([r[9]] if has_ip else []) + ([r[12]] if has_i2l else [])
            city_matches = ([r[7]] if has_mm else []) + ([r[13]] if has_i2l else [])
            country_all.extend(country_matches)
            city_all.extend(city_matches)
            w_country_all.extend((m, n) for m in country_matches)
            w_city_all.extend((m, n) for m in city_matches)
            # Per-provider tracking
            for key, match_idx in provider_indices:
                prov[key].append(r[match_idx])
                w_prov[key].append((r[match_idx], n))
            if r[1]:
                v6 += 1
                v6_addrs += n
                country_v6.extend(country_matches)
                city_v6.extend(city_matches)
                w_country_v6.extend((m, n) for m in country_matches)
                w_city_v6.extend((m, n) for m in city_matches)
            else:
                v4 += 1
                v4_addrs += n
                country_v4.extend(country_matches)
                city_v4.extend(city_matches)
                w_country_v4.extend((m, n) for m in country_matches)
                w_city_v4.extend((m, n) for m in city_matches)
    s = {
        "total": total, "v4": v4, "v6": v6,
        "v4_addrs": v4_addrs, "v6_addrs": v6_addrs,
        "country_pct": compute_pct(country_all),
        "country_pct_v4": compute_pct(country_v4),
        "country_pct_v6": compute_pct(country_v6),
        "city_pct": compute_pct(city_all),
        "city_pct_v4": compute_pct(city_v4),
        "city_pct_v6": compute_pct(city_v6),
        "w_country_pct": compute_weighted_pct(w_country_all),
        "w_country_pct_v4": compute_weighted_pct(w_country_v4),
        "w_country_pct_v6": compute_weighted_pct(w_country_v6),
        "w_city_pct": compute_weighted_pct(w_city_all),
        "w_city_pct_v4": compute_weighted_pct(w_city_v4),
        "w_city_pct_v6": compute_weighted_pct(w_city_v6),
    }
    for key in prov:
        s[key] = compute_pct(prov[key])
        s["w_" + key] = compute_weighted_pct(w_prov[key])
    return s


def compute_pct(matches):
    evaluated = [m for m in matches if m is not None]
    if not evaluated:
        return None
    return sum(1 for m in evaluated if m) / len(evaluated) * 100


def compute_weighted_pct(weighted_matches):
    """Compute accuracy weighted by address count. Input: list of (match_bool, num_addresses)."""
    evaluated = [(m, w) for m, w in weighted_matches if m is not None]
    if not evaluated:
        return None
    total_w = sum(w for _, w in evaluated)
    correct_w = sum(w for m, w in evaluated if m)
    return correct_w / total_w * 100


def pct_cell(pct, provider_start=False):
    ps = ' provider-start' if provider_start else ''
    if pct is None:
        return f'<td class="na{ps}">N/A</td>'
    if pct >= 90:
        cls = "good"
    elif pct >= 50:
        cls = "warn"
    else:
        cls = "bad"
    return f'<td class="{cls}{ps}">{pct:.1f}%</td>'


def _pct_cls(pct):
    if pct is None:
        return "na"
    if pct >= 90:
        return "good"
    return "warn" if pct >= 50 else "bad"


def _fmt_pct(pct):
    return "N/A" if pct is None else f"{pct:.1f}%"


def _fmt_addrs(n, is_v6):
    """Human-friendly address count: SI suffixes for IPv4, scientific notation for IPv6."""
    if is_v6:
        exp = len(str(n)) - 1
        mantissa = n / 10**exp
        return f"{mantissa:.1f} &times; 10<sup>{exp}</sup>"
    suffixes = [(1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")]
    for threshold, suffix in suffixes:
        if n >= threshold:
            return f"{n / threshold:.1f}{suffix}"
    return str(n)


def _favicon_uri(path):
    """Return a base64 data URI for a favicon file."""
    if not path.exists():
        return ""
    data = base64.b64encode(path.read_bytes()).decode()
    ext = path.suffix.lstrip(".")
    mime = "image/x-icon" if ext == "ico" else f"image/{ext}"
    return f"data:{mime};base64,{data}"


def _col_widths(has_mm, has_ip, has_i2l):
    """Return (first_col_pct, other_col_pct) for table-layout: fixed."""
    ncols = (2 if has_mm else 0) + (2 if has_ip else 0) + (2 if has_i2l else 0)
    if ncols == 0:
        return (100, 0)
    other = round(50 / ncols, 1)
    return (100 - ncols * other, other)


def match_cell(val, provider_val, provider_start=False):
    ps = ' provider-start' if provider_start else ''
    if val is None:
        return f'<td class="na{ps}">{provider_val or "N/A"}</td>'
    cls = "good" if val else "bad"
    return f'<td class="{cls}{ps}">{provider_val}</td>'


def generate_html(results, stats, has_mm=True, has_ip=True, has_i2l=True, feed=None):
    logo_file = feed["logo_file"] if feed else AWS_LOGO_FILE
    logo_type = feed.get("logo_type", "svg") if feed else "svg"
    title = feed["title"] if feed else "Geofeed Monitoring Report"
    topbar_title = feed.get("topbar_title", title) if feed else title
    output_path = feed["output"] if feed else Path("./index.html")

    if logo_file.exists():
        if logo_type == "svg":
            svg_text = logo_file.read_text(encoding="utf-8")
            logo_b64 = base64.b64encode(svg_text.encode()).decode()
            favicon_uri = f"data:image/svg+xml;base64,{logo_b64}"
            if feed and feed.get("logo_invert"):
                topbar_logo = f'<div style="filter:invert(1);display:flex;align-items:center">{svg_text}</div>'
            else:
                topbar_logo = svg_text
        else:
            raw = logo_file.read_bytes()
            b64 = base64.b64encode(raw).decode()
            invert = ' style="height:40px;filter:invert(1)"' if feed and feed.get("logo_invert") else ' style="height:40px"'
            topbar_logo = f'<img src="data:image/png;base64,{b64}"{invert} alt="">'
            favicon_uri = f"data:image/png;base64,{b64}"
    else:
        topbar_logo = ""
        favicon_uri = ""

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    html = []
    html.append(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
{f'<link rel="icon" href="{favicon_uri}">' if favicon_uri else ''}
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/lipis/flag-icons@7.2.3/css/flag-icons.min.css">
<style>
  :root {{
    --squid-ink: #232f3e;
    --squid-ink-light: #37475a;
    --aws-orange: #ff9900;
    --aws-orange-hover: #ec7211;
    --text-primary: #16191f;
    --text-secondary: #545b64;
    --bg-page: #f2f3f3;
    --bg-card: #ffffff;
    --border: #d5dbdb;
    --border-light: #eaeded;
    --good: #037f0c;
    --good-bg: #f2fcf3;
    --warn: #8a6d00;
    --warn-bg: #fef8e7;
    --bad: #d13212;
    --bad-bg: #fdf3f1;
    --na-text: #879596;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: "Amazon Ember", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: var(--bg-page);
    color: var(--text-primary);
    line-height: 1.5;
  }}
  .topbar {{
    background: var(--squid-ink);
    padding: 12px 32px;
    display: flex;
    align-items: center;
    gap: 16px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.15);
  }}
  .topbar svg {{ height: 40px; width: auto; }}
  .topbar h1 {{
    color: #ffffff;
    font-size: 20px;
    font-weight: 700;
    letter-spacing: -0.2px;
  }}
  .topbar .separator {{
    width: 1px;
    height: 28px;
    background: var(--squid-ink-light);
  }}
  .container {{
    max-width: 1400px;
    margin: 0 auto;
    padding: 24px 32px;
  }}
  .card {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05);
  }}
  .card-header {{
    padding: 16px 24px;
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    justify-content: space-between;
  }}
  .card-header h2 {{
    font-size: 18px;
    font-weight: 700;
    color: var(--text-primary);
  }}
  .filter-toggle {{
    font-size: 13px;
    color: var(--text-secondary);
    cursor: pointer;
    user-select: none;
    white-space: nowrap;
  }}
  .search-box {{
    font-size: 13px;
    padding: 5px 10px;
    border: 1px solid var(--border);
    border-radius: 6px;
    outline: none;
    width: 180px;
    font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
  }}
  .search-box:focus {{ border-color: var(--aws-orange); }}
  .filter-toggle input {{ vertical-align: middle; margin-right: 4px; cursor: pointer; }}
  .loc-filter {{
    font-size: 11px;
    color: var(--text-secondary);
    cursor: pointer;
    user-select: none;
    margin-left: 8px;
    font-weight: 400;
    display: none;
  }}
  .loc-row.open .loc-filter {{ display: inline; }}
  .loc-filter input {{ vertical-align: middle; margin-right: 2px; cursor: pointer; }}
  .loc-counter {{
    font-size: 11px;
    font-weight: 400;
    color: var(--text-secondary);
  }}
  .header-counter {{
    font-size: 11px;
    font-weight: 400;
    opacity: 0.7;
  }}
  .loc-row.filtered, .prefix-row.filtered {{ display: none !important; }}
  table {{ border-collapse: collapse; width: 100%; table-layout: fixed; }}
  th:first-child, td:first-child {{ width: {_col_widths(has_mm, has_ip, has_i2l)[0]}%; }}
  th:not(:first-child), td:not(:first-child) {{ width: {_col_widths(has_mm, has_ip, has_i2l)[1]}%; }}
  th {{
    background: var(--squid-ink);
    color: #fff;
    padding: 10px 16px;
    font-size: 13px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    position: sticky;
    top: 0;
    z-index: 10;
  }}
  th.provider-hdr {{
    text-align: center;
    border-left: 2px solid var(--squid-ink-light);
    background: var(--squid-ink);
    font-size: 13px;
    text-transform: uppercase;
  }}
  th.provider-hdr img {{
    height: 16px;
    width: 16px;
    vertical-align: middle;
    margin-right: 6px;
  }}
  th.sub-hdr {{
    text-align: center;
    font-size: 11px;
    background: var(--squid-ink-light);
    text-transform: none;
    letter-spacing: 0;
    font-weight: 500;
  }}
  th.sub-hdr.provider-start {{ border-left: 2px solid var(--squid-ink-light); }}
  td {{
    padding: 10px 16px;
    font-size: 14px;
    border-bottom: 1px solid var(--border-light);
    color: var(--text-primary);
  }}
  .loc-row {{
    cursor: pointer;
    background: var(--bg-card);
    transition: background 0.15s;
  }}
  .loc-row:hover {{ background: #f7f8f8; }}
  .loc-row td {{ font-weight: 600; }}
  .loc-row td:first-child {{
    padding-left: 20px;
  }}
  .loc-row td:first-child::before {{
    content: "";
    display: inline-block;
    width: 0; height: 0;
    margin-right: 10px;
    border-left: 6px solid var(--aws-orange);
    border-top: 4px solid transparent;
    border-bottom: 4px solid transparent;
    transition: transform 0.2s;
    vertical-align: middle;
  }}
  .loc-row.open td:first-child::before {{
    transform: rotate(90deg);
  }}
  .prefix-row {{ display: none; }}
  .prefix-row.show {{ display: table-row; }}
  .prefix-row td {{ background: #fafbfc; }}
  .prefix-row td:first-child {{
    padding-left: 44px;
    font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
    font-size: 13px;
    color: var(--text-secondary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }}
  .prefix-row td:first-child small {{
    color: var(--na-text);
    font-family: "Amazon Ember", -apple-system, sans-serif;
  }}
  td.good {{ color: var(--good); background: var(--good-bg); font-weight: 600; }}
  td.warn {{ color: var(--warn); background: var(--warn-bg); font-weight: 600; }}
  td.bad {{ color: var(--bad); background: var(--bad-bg); font-weight: 600; }}
  td.na {{ color: var(--na-text); }}
  td.provider-start {{ border-left: 2px solid var(--border-light); }}
  .loc-row td.provider-start {{ border-left: 2px solid var(--border); }}
  td {{ text-align: center; }}
  td:first-child {{ text-align: left; }}
  .stats-bar {{
    display: grid;
    grid-template-columns: auto repeat(3, 1fr);
    gap: 0;
    border-bottom: 1px solid var(--border);
    background: var(--bg-page);
  }}
  .stats-row-label {{
    display: flex;
    align-items: center;
    padding: 16px 20px;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--text-secondary);
    border-bottom: 1px solid var(--border);
  }}
  .stats-row-label:last-of-type,
  .stats-bar .stat-group:nth-last-child(-n+3) {{
    border-bottom: none;
  }}
  .stat-group {{
    min-width: 0;
    padding: 14px 24px;
    border-bottom: 1px solid var(--border);
  }}
  .stat-group-title {{
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--text-secondary);
    margin-bottom: 6px;
  }}
  .stat-items {{ display: flex; gap: 16px; }}
  .stat {{ display: flex; flex-direction: column; }}
  .stat-value {{
    font-size: 20px;
    font-weight: 700;
    color: var(--text-primary);
    line-height: 1.2;
  }}
  .stat-value.good {{ color: var(--good); }}
  .stat-value.warn {{ color: var(--warn); }}
  .stat-value.bad {{ color: var(--bad); }}
  .stat-label {{
    font-size: 11px;
    color: var(--text-secondary);
  }}
  tfoot td {{
    background: var(--bg-page);
    font-size: 12px;
    font-weight: 600;
    padding: 8px 16px;
    border-top: 2px solid var(--border);
    color: var(--text-secondary);
  }}
  tfoot td.good {{ color: var(--good); background: var(--good-bg); }}
  tfoot td.warn {{ color: var(--warn); background: var(--warn-bg); }}
  tfoot td.bad {{ color: var(--bad); background: var(--bad-bg); }}
  tfoot td.na {{ color: var(--na-text); }}
</style>
</head>
<body>
<div class="topbar">
  {topbar_logo}
  <div class="separator"></div>
  <h1>{topbar_title}</h1>
</div>
<div class="container">
<div class="card">
<div class="card-header">
  <h2>Location Validation Results</h2>
  <div style="display:flex;align-items:center;gap:12px">
    <input type="text" id="prefixSearch" placeholder="Search prefix or IP…" class="search-box">
    <label class="filter-toggle"><input type="checkbox" id="globalFilter"> Show only inaccurate</label>
  </div>
</div>
<div class="stats-bar">
  <div class="stats-row-label">Prefixes</div>
  <div class="stat-group">
    <div class="stat-group-title">Count</div>
    <div class="stat-items">
      <div class="stat"><span class="stat-value">{stats['total']:,}</span><span class="stat-label">Total</span></div>
      <div class="stat"><span class="stat-value">{stats['v4']:,}</span><span class="stat-label">IPv4</span></div>
      <div class="stat"><span class="stat-value">{stats['v6']:,}</span><span class="stat-label">IPv6</span></div>
    </div>
  </div>
  <div class="stat-group">
    <div class="stat-group-title">Country Accuracy</div>
    <div class="stat-items">
      <div class="stat"><span class="stat-value {_pct_cls(stats['country_pct'])}">{_fmt_pct(stats['country_pct'])}</span><span class="stat-label">Total</span></div>
      <div class="stat"><span class="stat-value {_pct_cls(stats['country_pct_v4'])}">{_fmt_pct(stats['country_pct_v4'])}</span><span class="stat-label">IPv4</span></div>
      <div class="stat"><span class="stat-value {_pct_cls(stats['country_pct_v6'])}">{_fmt_pct(stats['country_pct_v6'])}</span><span class="stat-label">IPv6</span></div>
    </div>
  </div>
  <div class="stat-group">
    <div class="stat-group-title">City Accuracy</div>
    <div class="stat-items">
      <div class="stat"><span class="stat-value {_pct_cls(stats['city_pct'])}">{_fmt_pct(stats['city_pct'])}</span><span class="stat-label">Total</span></div>
      <div class="stat"><span class="stat-value {_pct_cls(stats['city_pct_v4'])}">{_fmt_pct(stats['city_pct_v4'])}</span><span class="stat-label">IPv4</span></div>
      <div class="stat"><span class="stat-value {_pct_cls(stats['city_pct_v6'])}">{_fmt_pct(stats['city_pct_v6'])}</span><span class="stat-label">IPv6</span></div>
    </div>
  </div>
  <div class="stats-row-label">Addresses</div>
  <div class="stat-group">
    <div class="stat-group-title">Count</div>
    <div class="stat-items">
      <div class="stat"><span class="stat-value">{_fmt_addrs(stats['v4_addrs'], False)}</span><span class="stat-label">IPv4</span></div>
      <div class="stat"><span class="stat-value">{_fmt_addrs(stats['v6_addrs'], True)}</span><span class="stat-label">IPv6</span></div>
    </div>
  </div>
  <div class="stat-group">
    <div class="stat-group-title">Country Accuracy</div>
    <div class="stat-items">
      <div class="stat"><span class="stat-value {_pct_cls(stats['w_country_pct'])}">{_fmt_pct(stats['w_country_pct'])}</span><span class="stat-label">Total</span></div>
      <div class="stat"><span class="stat-value {_pct_cls(stats['w_country_pct_v4'])}">{_fmt_pct(stats['w_country_pct_v4'])}</span><span class="stat-label">IPv4</span></div>
      <div class="stat"><span class="stat-value {_pct_cls(stats['w_country_pct_v6'])}">{_fmt_pct(stats['w_country_pct_v6'])}</span><span class="stat-label">IPv6</span></div>
    </div>
  </div>
  <div class="stat-group">
    <div class="stat-group-title">City Accuracy</div>
    <div class="stat-items">
      <div class="stat"><span class="stat-value {_pct_cls(stats['w_city_pct'])}">{_fmt_pct(stats['w_city_pct'])}</span><span class="stat-label">Total</span></div>
      <div class="stat"><span class="stat-value {_pct_cls(stats['w_city_pct_v4'])}">{_fmt_pct(stats['w_city_pct_v4'])}</span><span class="stat-label">IPv4</span></div>
      <div class="stat"><span class="stat-value {_pct_cls(stats['w_city_pct_v6'])}">{_fmt_pct(stats['w_city_pct_v6'])}</span><span class="stat-label">IPv6</span></div>
    </div>
  </div>
</div>
<table>
<thead>
<tr>
  <th rowspan="2">Location <span id="locCounter" class="header-counter"></span></th>
  {'<th colspan="2" class="provider-hdr"><img src="' + _favicon_uri(MAXMIND_FAVICON_FILE) + '" alt="">MaxMind</th>' if has_mm else ''}
  {'<th colspan="2" class="provider-hdr"><img src="' + _favicon_uri(IPINFO_FAVICON_FILE) + '" alt="">IPinfo</th>' if has_ip else ''}
  {'<th colspan="2" class="provider-hdr"><img src="' + _favicon_uri(IP2LOCATION_FAVICON_FILE) + '" alt="">IP2Location</th>' if has_i2l else ''}
</tr>
<tr>
  {'<th class="sub-hdr provider-start">Country</th><th class="sub-hdr">City</th>' if has_mm else ''}
  {'<th class="sub-hdr provider-start">Country</th><th class="sub-hdr">City</th>' if has_ip else ''}
  {'<th class="sub-hdr provider-start">Country</th><th class="sub-hdr">City</th>' if has_i2l else ''}
</tr>
</thead><tbody>""")

    for loc_idx, (country_code, display_name, loc_results) in enumerate(results):
        if not loc_results:
            continue

        mm_c_pct = compute_pct([r[6] for r in loc_results])
        mm_ci_pct = compute_pct([r[7] for r in loc_results])
        ip_c_pct = compute_pct([r[9] for r in loc_results])
        i2l_c_pct = compute_pct([r[12] for r in loc_results])
        i2l_ci_pct = compute_pct([r[13] for r in loc_results])

        checks = []
        if has_mm: checks += [(6,), (7,)]
        if has_ip: checks += [(9,)]
        if has_i2l: checks += [(12,), (13,)]
        active = [i for (i,) in checks]
        has_bad = any(
            any(r[i] is not None and not r[i] for i in active)
            for r in loc_results
        )
        html.append(f'<tr class="loc-row" data-loc="{loc_idx}" data-has-bad="{int(has_bad)}">')
        cc = country_code.lower()
        flag = f'<span class="fi fi-{cc}" style="margin-right:8px"></span>'
        loc_filter = f'<label class="loc-filter"><input type="checkbox" class="locFilter" data-loc="{loc_idx}"> inaccurate only</label>'
        html.append(f"  <td>{flag}{display_name} <span class='loc-count' data-loc-count='{loc_idx}' data-total='{len(loc_results)}'>({len(loc_results)})</span> {loc_filter}</td>")
        if has_mm:
            html.append(f'  {pct_cell(mm_c_pct, True)}{pct_cell(mm_ci_pct)}')
        if has_ip:
            html.append(f'  {pct_cell(ip_c_pct, True)}<td class="na">N/A</td>')
        if has_i2l:
            html.append(f'  {pct_cell(i2l_c_pct, True)}{pct_cell(i2l_ci_pct)}')
        html.append("</tr>")

        for r in sorted(loc_results, key=lambda r: (r[1], r[0])):
            prefix, is_v6, gf_c, gf_ci = r[0], r[1], r[2], r[3]
            mm_c, mm_ci, mm_c_m, mm_ci_m = r[4], r[5], r[6], r[7]
            ip_c, ip_c_m = r[8], r[9]
            i2l_c, i2l_ci, i2l_c_m, i2l_ci_m = r[10], r[11], r[12], r[13]
            proto = "IPv6" if is_v6 else "IPv4"
            active_m = ([mm_c_m, mm_ci_m] if has_mm else []) + ([ip_c_m] if has_ip else []) + ([i2l_c_m, i2l_ci_m] if has_i2l else [])
            perfect = all(m is None or m for m in active_m)
            html.append(f'<tr class="prefix-row" data-loc="{loc_idx}" data-perfect="{int(perfect)}" data-prefix="{prefix}">')
            html.append(f"  <td>{prefix} <small>({proto}) &mdash; geofeed: {gf_c}, {gf_ci}</small></td>")
            if has_mm:
                html.append(f'  {match_cell(mm_c_m, mm_c, True)}{match_cell(mm_ci_m, mm_ci)}')
            if has_ip:
                html.append(f'  {match_cell(ip_c_m, ip_c, True)}<td class="na">N/A</td>')
            if has_i2l:
                html.append(f'  {match_cell(i2l_c_m, i2l_c, True)}{match_cell(i2l_ci_m, i2l_ci)}')
            html.append("</tr>")

    html.append("</tbody>")

    # Table footer with per-provider accuracy
    def _foot_label(label):
        return f'<td style="text-align:right;font-weight:700;font-size:11px;text-transform:uppercase;letter-spacing:0.5px">{label}</td>'

    def _foot_row(label, mm_c_key, mm_ci_key, ip_c_key, i2l_c_key, i2l_ci_key):
        row = f'<tr>{_foot_label(label)}'
        if has_mm:
            row += pct_cell(stats.get(mm_c_key), True) + pct_cell(stats.get(mm_ci_key))
        if has_ip:
            row += pct_cell(stats.get(ip_c_key), True) + '<td class="na">N/A</td>'
        if has_i2l:
            row += pct_cell(stats.get(i2l_c_key), True) + pct_cell(stats.get(i2l_ci_key))
        row += '</tr>'
        return row

    html.append('<tfoot>')
    html.append(_foot_row('Prefix Accuracy', 'mm_c', 'mm_ci', 'ip_c', 'i2l_c', 'i2l_ci'))
    html.append(_foot_row('Address Accuracy', 'w_mm_c', 'w_mm_ci', 'w_ip_c', 'w_i2l_c', 'w_i2l_ci'))
    html.append('</tfoot>')

    html.append(f"""</table>
</div>
</div>
<footer style="text-align:center;padding:16px;font-size:12px;color:#545b64">
  Last updated: {now_utc}
</footer>""")

    html.append("""<script>
function parseIP(s) {
  if (s.includes(':')) {
    const parts = s.split(':');
    const full = [];
    for (let i = 0; i < parts.length; i++) {
      if (parts[i] === '') {
        const fill = 8 - parts.filter(p => p !== '').length;
        for (let j = 0; j < fill; j++) full.push(0n);
      } else {
        full.push(BigInt(parseInt(parts[i], 16)));
      }
    }
    if (full.length !== 8) return null;
    let n = 0n;
    for (const p of full) n = (n << 16n) | p;
    return { bits: n, ver: 6 };
  }
  const p = s.split('.');
  if (p.length !== 4 || p.some(x => isNaN(x) || x < 0 || x > 255 || x === '')) return null;
  return { bits: BigInt(p[0]) << 24n | BigInt(p[1]) << 16n | BigInt(p[2]) << 8n | BigInt(p[3]), ver: 4 };
}
function parsePrefix(cidr) {
  const [addr, lenStr] = cidr.split('/');
  const ip = parseIP(addr);
  if (!ip) return null;
  const len = BigInt(lenStr);
  const total = ip.ver === 6 ? 128n : 32n;
  const mask = ((1n << total) - 1n) ^ ((1n << (total - len)) - 1n);
  return { net: ip.bits & mask, mask, ver: ip.ver };
}
function ipInPrefix(ip, prefix) {
  if (ip.ver !== prefix.ver) return false;
  return (ip.bits & prefix.mask) === prefix.net;
}
function applyFilters() {
  const globalOn = document.getElementById('globalFilter').checked;
  const query = document.getElementById('prefixSearch').value.trim().toLowerCase();
  const searching = query.length > 0;
  const filtering = globalOn || searching;
  const searchIP = searching ? parseIP(query) : null;
  let visibleLocs = 0, totalLocs = 0;
  document.querySelectorAll('.loc-row').forEach(row => {
    const id = row.dataset.loc;
    const hasBad = row.dataset.hasBad === '1';
    const prefixes = document.querySelectorAll(`.prefix-row[data-loc="${id}"]`);
    const local = row.querySelector('.locFilter');
    const localOn = local && local.checked;
    const countEl = document.querySelector(`[data-loc-count="${id}"]`);
    const total = prefixes.length;
    let visible = 0;
    prefixes.forEach(r => {
      let hidden = false;
      if ((globalOn || localOn) && r.dataset.perfect === '1') hidden = true;
      if (searching) {
        let match = r.dataset.prefix.indexOf(query) !== -1;
        if (!match && searchIP) {
          const pfx = parsePrefix(r.dataset.prefix);
          if (pfx) match = ipInPrefix(searchIP, pfx);
        }
        if (!match) hidden = true;
      }
      r.classList.toggle('filtered', hidden);
      if (!hidden) visible++;
    });
    const hideRow = (globalOn && !hasBad) || (searching && visible === 0);
    row.classList.toggle('filtered', hideRow);
    totalLocs++;
    if (!hideRow) visibleLocs++;
    const isFiltered = (globalOn || localOn || searching) && visible < total;
    countEl.textContent = isFiltered ? `(${visible} / ${total})` : `(${total})`;
    if (searching && visible > 0 && !row.classList.contains('open')) {
      row.classList.add('open');
      prefixes.forEach(r => r.classList.add('show'));
    }
  });
  const hdr = document.getElementById('locCounter');
  hdr.textContent = filtering ? `${visibleLocs} / ${totalLocs}` : '';
}
document.getElementById('globalFilter').addEventListener('change', applyFilters);
document.getElementById('prefixSearch').addEventListener('input', applyFilters);
document.querySelectorAll('.locFilter').forEach(cb => {
  cb.addEventListener('change', e => { e.stopPropagation(); applyFilters(); });
  cb.addEventListener('click', e => e.stopPropagation());
});
document.querySelectorAll('.loc-filter').forEach(lbl => {
  lbl.addEventListener('click', e => e.stopPropagation());
});
document.querySelectorAll('.loc-row').forEach(row => {
  row.addEventListener('click', () => {
    const id = row.dataset.loc;
    row.classList.toggle('open');
    document.querySelectorAll(`.prefix-row[data-loc="${id}"]`).forEach(r => r.classList.toggle('show'));
  });
});
</script>
</body></html>""")

    output_path.write_text("\n".join(html), encoding="utf-8")


if __name__ == "__main__":
    main()
