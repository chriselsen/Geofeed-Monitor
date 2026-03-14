"""UN/LOCODE validation for geofeed entries."""

import csv
import functools
import io
import re
import unicodedata
import zipfile
from collections import defaultdict
from urllib.request import urlopen

LOCODE_URL = "https://service.unece.org/trade/locode/loc242csv.zip"
LOCODE_PARTS = [
    "2024-2 UNLOCODE CodeListPart1.csv",
    "2024-2 UNLOCODE CodeListPart2.csv",
    "2024-2 UNLOCODE CodeListPart3.csv",
]

_db = None  # (country, norm_city) -> set of subdivision codes


def _normalize(s):
    s = re.sub(r'\s*\(.*?\)', '', s)   # strip parenthetical suffixes
    s = re.sub(r'\s*=.*', '', s)       # strip "= alternate name" suffixes
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().strip().lower()


def load_locode():
    global _db
    if _db is not None:
        return
    print("Loading UN/LOCODE data...")
    data = urlopen(LOCODE_URL).read()
    db = defaultdict(set)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for part in LOCODE_PARTS:
            text = zf.read(part).decode("latin-1")
            for row in csv.reader(io.StringIO(text)):
                if len(row) < 6:
                    continue
                country = row[1].strip()
                location = row[2].strip()
                name = row[4].strip()   # NameWoDiacritics
                subdiv = row[5].strip()
                if not country or not name:
                    continue
                db[(country, _normalize(name))].add(subdiv)
    _db = db
    print(f"  Loaded {len(_db)} UN/LOCODE entries")


@functools.lru_cache(maxsize=None)
def validate_locode(gf_country, gf_subdiv, gf_city):
    """
    Validate a geofeed entry against UN/LOCODE.
    Returns a tuple of issue strings, empty if all OK or city is blank.
    """
    if not gf_city:
        return ()

    load_locode()
    norm_city = _normalize(gf_city)

    all_countries_for_city = {c: subdivs for (c, n), subdivs in _db.items() if n == norm_city}

    if not all_countries_for_city:
        return (f'City "{gf_city}" not found in UN/LOCODE',)

    # City exists but not in the claimed country
    if gf_country not in all_countries_for_city:
        known = ", ".join(sorted(all_countries_for_city.keys()))
        return (f'City "{gf_city}" not found in country {gf_country} (known in: {known})',)

    # Subdivision mismatch
    if gf_subdiv:
        subdiv_code = gf_subdiv.split("-", 1)[-1] if "-" in gf_subdiv else gf_subdiv
        known_with_subdiv = {s for s in all_countries_for_city[gf_country] if s}
        if known_with_subdiv and subdiv_code not in known_with_subdiv:
            known_fmt = ", ".join(f"{gf_country}-{s}" for s in sorted(known_with_subdiv))
            return (f'City "{gf_city}" not found in region {gf_subdiv} (known in: {known_fmt})',)

    return ()
