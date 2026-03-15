"""Compute accuracy statistics from validation results."""

import ipaddress


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
        provider_indices += [("mm_c", 7), ("mm_ci", 8)]
    if has_ip:
        provider_indices += [("ip_c", 10)]
    if has_i2l:
        provider_indices += [("i2l_c", 13), ("i2l_ci", 14)]
    prov = {k: [] for k, _ in provider_indices}
    w_prov = {k: [] for k, _ in provider_indices}
    for _, _, loc_results in results:
        for r in loc_results:
            net = ipaddress.ip_network(r[0], strict=False)
            n = net.num_addresses
            total += 1
            country_matches = ([r[7]] if has_mm else []) + ([r[10]] if has_ip else []) + ([r[13]] if has_i2l else [])
            city_matches = ([r[8]] if has_mm else []) + ([r[14]] if has_i2l else [])
            country_all.extend(country_matches)
            city_all.extend(city_matches)
            w_country_all.extend((m, n) for m in country_matches)
            w_city_all.extend((m, n) for m in city_matches)
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
        "routed": sum(1 for _, _, lr in results for r in lr if r[16] and not r[18]),
        "unrouted": sum(1 for _, _, lr in results for r in lr if not r[16] and not r[18]),
        "too_specific": sum(1 for _, _, lr in results for r in lr if r[18]),
        "locode_errors": sum(1 for _, _, lr in results for r in lr if r[15]),
        "rfc9092": sum(1 for _, _, lr in results for r in lr if r[19] is not None),
    }
    for key in prov:
        s[key] = compute_pct(prov[key])
        s["w_" + key] = compute_weighted_pct(w_prov[key])
    return s
