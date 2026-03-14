"""Download and query geolocation databases (MaxMind, IPinfo, IP2Location)."""

import os
import subprocess
import tarfile
import zipfile

from .config import (
    ASSETS_DIR, MAXMIND_DOWNLOAD_URL, MAXMIND_DIR, MAXMIND_DB_FILE,
    IPINFO_DOWNLOAD_URL, IPINFO_DIR, IPINFO_DB_FILE,
    IP2LOCATION_DOWNLOAD_URL_V6, IP2LOCATION_DIR, IP2LOCATION_DB_FILE,
    AWS_LOGO_FILE, AWS_LOGO_URL, AWS_CARD_LOGO_FILE, AWS_CARD_LOGO_URL,
    AS213151_LOGO_FILE, AS213151_LOGO_URL, STARLINK_LOGO_FILE, STARLINK_LOGO_URL,
    MICROSOFT_LOGO_FILE, MICROSOFT_LOGO_URL,
    MAXMIND_FAVICON_FILE, MAXMIND_FAVICON_URL,
    IPINFO_FAVICON_FILE, IPINFO_FAVICON_URL,
    IP2LOCATION_FAVICON_FILE, IP2LOCATION_FAVICON_URL,
)


def update_maxmind():
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


def update_ipinfo():
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


def update_ip2location():
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


def download_assets():
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    for path, url in [
        (AWS_LOGO_FILE, AWS_LOGO_URL),
        (AWS_CARD_LOGO_FILE, AWS_CARD_LOGO_URL),
        (AS213151_LOGO_FILE, AS213151_LOGO_URL),
        (STARLINK_LOGO_FILE, STARLINK_LOGO_URL),
        (MICROSOFT_LOGO_FILE, MICROSOFT_LOGO_URL),
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


def lookup_maxmind(ip_str, mm_reader):
    result = mm_reader.get(ip_str)
    if not result:
        return (None, None)
    country = result.get("country", {}).get("iso_code")
    city = result.get("city", {}).get("names", {}).get("en")
    return (country, city)


def lookup_ipinfo(ip_str, ip_reader):
    result = ip_reader.get(ip_str)
    if not result:
        return (None, None)
    return (result.get("country_code"), None)


def lookup_ip2location(ip_str, i2l_reader):
    rec = i2l_reader.get_all(ip_str)
    if not rec:
        return (None, None)
    country = rec.country_short if rec.country_short not in ("-", "?") else None
    city = rec.city if rec.city not in ("-", "?") else None
    return (country, city)
