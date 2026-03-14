"""BGP routing visibility check using RIPE RIS whois dumps."""

import gzip
import io
from urllib.request import urlopen

import pytricia

RIS_IPV4_URL = "https://www.ris.ripe.net/dumps/riswhoisdump.IPv4.gz"
RIS_IPV6_URL = "https://www.ris.ripe.net/dumps/riswhoisdump.IPv6.gz"
MIN_PEERS = 2  # minimum RIS peers required to consider a prefix routed

_trie4 = None
_trie6 = None


def _load_dump(url, trie):
    data = urlopen(url).read()
    for line in gzip.decompress(data).decode("ascii").splitlines():
        if not line or line.startswith("%"):
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        prefix, peers = parts[1], int(parts[2])
        if peers >= MIN_PEERS:
            try:
                trie[prefix] = peers
            except ValueError:
                pass


def load_routing_table():
    global _trie4, _trie6
    if _trie4 is not None:
        return
    print("Loading RIPE RIS routing table...")
    _trie4 = pytricia.PyTricia(32)
    _trie6 = pytricia.PyTricia(128)
    _load_dump(RIS_IPV4_URL, _trie4)
    _load_dump(RIS_IPV6_URL, _trie6)
    print(f"  Loaded {len(_trie4):,} IPv4 and {len(_trie6):,} IPv6 prefixes")


def is_routed(prefix, is_v6):
    """Return True and the matched prefix if visible, else False and None."""
    load_routing_table()
    trie = _trie6 if is_v6 else _trie4
    # Check exact match or covering supernet via longest-prefix match on network address
    # Exclude default route (0.0.0.0/0 or ::/0) which would match everything
    match_key = trie.get_key(prefix.split('/')[0])
    if match_key is not None and match_key not in ('0.0.0.0/0', '::/0'):
        return True, match_key
    # Check for any more-specific by temporarily inserting the prefix
    trie[prefix] = 0
    try:
        children = trie.children(prefix)
        found = len(children) > 0
        match_key = children[0] if found else None
    except KeyError:
        found = False
        match_key = None
    finally:
        del trie[prefix]
    return found, match_key
