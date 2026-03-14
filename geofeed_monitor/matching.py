"""Country/city matching and prefix validation."""

import ipaddress
import unicodedata

from .providers import lookup_maxmind, lookup_ipinfo, lookup_ip2location
from .routing import is_routed
from .unlocode import validate_locode


def match_country(gf_country, provider_country):
    if not provider_country:
        return None
    return gf_country.strip().upper() == provider_country.strip().upper()


def _normalize(s):
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().strip().lower()


def match_city(gf_city, provider_city):
    if not provider_city:
        return None
    return _normalize(gf_city) == _normalize(provider_city)


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

            locode_issues = validate_locode(gf_country, gf_subdiv, gf_city)
            routed, route_match = is_routed(prefix, net.version == 6)
            too_specific = (net.version == 4 and net.prefixlen > 24) or (net.version == 6 and net.prefixlen > 48)
            loc_results.append((
                prefix, net.version == 6, gf_country, gf_subdiv, gf_city,
                mm_country or "", mm_city or "",
                match_country(gf_country, mm_country), match_city(gf_city, mm_city),
                ip_country or "", match_country(gf_country, ip_country),
                i2l_country or "", i2l_city or "",
                match_country(gf_country, i2l_country), match_city(gf_city, i2l_city),
                locode_issues, routed, route_match, too_specific,
            ))
            done += 1
            if done % 500 == 0:
                print(f"  {done}/{total} prefixes validated...", end="\r")
        results.append((country_code, display_name, loc_results))
    print(f"  {done}/{total} prefixes validated.    ")
    return results
