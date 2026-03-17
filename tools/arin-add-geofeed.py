#!/usr/bin/env python3
"""
Add, update, or remove RFC 9092 Geofeed remarks on ARIN network records.

Usage:
    python3 arin-add-geofeed.py --org AL-3043 --geofeed https://geofeed.as213151.net/geofeed.txt
    python3 arin-add-geofeed.py --org AL-3043 --geofeed https://geofeed.as213151.net/geofeed.txt --update
    python3 arin-add-geofeed.py --org AL-3043 --geofeed https://geofeed.as213151.net/geofeed.txt --root-only
    python3 arin-add-geofeed.py --org AL-3043 --remove
    python3 arin-add-geofeed.py --org AL-3043 --geofeed https://geofeed.as213151.net/geofeed.txt --dry-run
    python3 arin-add-geofeed.py --org AL-3043 --geofeed https://geofeed.as213151.net/geofeed.txt --prod

By default uses the ARIN OT&E (test) environment. Pass --prod to use production.
Requires ARIN_API_KEY environment variable.
"""

import argparse
import json
import os
import re
import sys
from urllib.request import urlopen, Request
from urllib.error import HTTPError
import xml.etree.ElementTree as ET

OTE_BASE  = "https://reg.ote.arin.net/rest"
PROD_BASE = "https://reg.arin.net/rest"
RDAP_BASE = "https://rdap.arin.net/registry"
NS = "http://www.arin.net/regrws/core/v1"

# Matches any line containing a Geofeed remark in the formats:
#   "Geofeed https://..."  (RFC 9092 standard)
#   "geofeed https://..."  (case-insensitive)
#   "Geofeed: https://..." (colon variant seen in some records)
# Used both for detection and for removal.
GEOFEED_RE = re.compile(r'[Gg]eofeed:?\s+https?://\S+')


def get_api_key():
    key = os.environ.get("ARIN_API_KEY")
    if not key:
        print("ERROR: ARIN_API_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)
    return key


def get_org_net_handles(org_handle):
    """Return all ARIN net handles for an org via RDAP."""
    url = f"{RDAP_BASE}/entity/{org_handle}"
    d = json.loads(urlopen(url, timeout=15).read())
    return [n["handle"] for n in d.get("networks", [])]


def get_net_record(base_url, handle, api_key):
    """Fetch a NET record XML from ARIN Reg-RWS."""
    url = f"{base_url}/net/{handle}?apikey={api_key}"
    req = Request(url, headers={"Accept": "application/xml"})
    return urlopen(req, timeout=15).read().decode("utf-8")


def is_root_record(xml_str, org_handle, base_url, api_key):
    """
    Return True if this net record's parent net is NOT owned by the same org.

    This identifies the outermost allocation registered under this org handle.
    For orgs with direct ARIN allocations this is the block allocated by ARIN.
    For orgs that received a delegation from another org (e.g. a provider
    sub-allocating to a customer), this returns True for the delegated block
    itself — i.e. the root is relative to the org, not to the global hierarchy.

    Fetches the parent net record via Reg-RWS and compares its orgHandle.
    Falls back to True (treat as root) if the parent cannot be fetched, to
    avoid silently skipping records due to transient network errors.
    """
    root = ET.fromstring(xml_str)
    parent_handle_el = root.find(f"{{{NS}}}parentNetHandle")
    if parent_handle_el is None or not parent_handle_el.text:
        return True
    parent_handle = parent_handle_el.text.strip()
    try:
        parent_xml = get_net_record(base_url, parent_handle, api_key)
        parent_root = ET.fromstring(parent_xml)
        parent_org_el = parent_root.find(f"{{{NS}}}orgHandle")
        if parent_org_el is not None and parent_org_el.text:
            return parent_org_el.text.strip() != org_handle
    except Exception:
        pass
    return True


def has_geofeed(xml_str):
    """Return the existing Geofeed line text if present in comments, else None."""
    root = ET.fromstring(xml_str)
    comment = root.find(f"{{{NS}}}comment")
    if comment is None:
        return None
    for line in comment.findall(f"{{{NS}}}line"):
        if line.text and GEOFEED_RE.search(line.text):
            return line.text.strip()
    return None


def build_added_xml(xml_str, geofeed_url):
    """Return XML with Geofeed line appended to comments.

    Only the <comment> element is modified. All other fields (netBlocks,
    orgHandle, pocLinks, parentNetHandle, etc.) are parsed and re-serialised
    unchanged, so the PUT payload is a safe round-trip of the original record.
    Line numbers are sequential integers; we append at max+1 to avoid conflicts.
    """
    root = ET.fromstring(xml_str)
    comment = root.find(f"{{{NS}}}comment")
    if comment is None:
        comment = ET.SubElement(root, f"{{{NS}}}comment")
    existing = comment.findall(f"{{{NS}}}line")
    next_num = max((int(l.get("number", 0)) for l in existing), default=-1) + 1
    new_line = ET.SubElement(comment, f"{{{NS}}}line")
    new_line.set("number", str(next_num))
    new_line.text = f"Geofeed {geofeed_url}"
    ET.register_namespace("", NS)
    return ET.tostring(root, encoding="unicode", xml_declaration=False)


def build_replaced_xml(xml_str, geofeed_url):
    """Return XML with all existing Geofeed lines replaced by a single canonical one.

    RFC 9092/9632 specifies exactly one Geofeed remark per record. If multiple
    Geofeed lines exist (non-compliant), this removes all of them and inserts
    a single canonical 'Geofeed <url>' line, ensuring the record is compliant.
    Line number is set to max_existing + 1.
    """
    root = ET.fromstring(xml_str)
    comment = root.find(f"{{{NS}}}comment")
    if comment is None:
        comment = ET.SubElement(root, f"{{{NS}}}comment")
    # Remove all existing Geofeed lines
    for line in comment.findall(f"{{{NS}}}line"):
        if line.text and GEOFEED_RE.search(line.text):
            comment.remove(line)
    # Add single canonical Geofeed line
    existing = comment.findall(f"{{{NS}}}line")
    next_num = max((int(l.get("number", 0)) for l in existing), default=-1) + 1
    new_line = ET.SubElement(comment, f"{{{NS}}}line")
    new_line.set("number", str(next_num))
    new_line.text = f"Geofeed {geofeed_url}"
    ET.register_namespace("", NS)
    return ET.tostring(root, encoding="unicode", xml_declaration=False)


def build_removed_xml(xml_str):
    """Return XML with all Geofeed comment lines removed.

    Removes every comment line matching GEOFEED_RE. Non-Geofeed comment lines
    (e.g. certificates, NOC contact info) are preserved unchanged.
    """
    root = ET.fromstring(xml_str)
    comment = root.find(f"{{{NS}}}comment")
    if comment is not None:
        for line in comment.findall(f"{{{NS}}}line"):
            if line.text and GEOFEED_RE.search(line.text):
                comment.remove(line)
    ET.register_namespace("", NS)
    return ET.tostring(root, encoding="unicode", xml_declaration=False)


def put_net_record(base_url, handle, api_key, xml_str):
    """PUT updated NET record to ARIN Reg-RWS.

    ARIN Reg-RWS expects a full NET payload on PUT — partial updates are not
    supported. The payload must include all fields from the original GET response.
    On success returns (response_body, None). On HTTP error returns (None, error_body).
    """
    url = f"{base_url}/net/{handle}?apikey={api_key}"
    body = f'<?xml version="1.0" encoding="UTF-8"?>{xml_str}'.encode("utf-8")
    req = Request(url, data=body, method="PUT",
                  headers={"Content-Type": "application/xml", "Accept": "application/xml"})
    try:
        return urlopen(req, timeout=15).read().decode("utf-8"), None
    except HTTPError as e:
        return None, e.read().decode("utf-8")


def main():
    parser = argparse.ArgumentParser(description="Add/update/remove RFC 9092 Geofeed remarks on ARIN net records")
    parser.add_argument("--org", required=True, help="ARIN org handle (e.g. AL-3043)")
    parser.add_argument("--geofeed", help="Geofeed URL to register (required unless --remove)")
    parser.add_argument("--update", action="store_true", help="Update existing Geofeed remarks pointing to a different URL")
    parser.add_argument("--root-only", action="store_true", help="Only update the root allocation (parent net not owned by this org)")
    parser.add_argument("--remove", action="store_true", help="Remove all Geofeed remarks regardless of URL")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be changed without making any changes")
    parser.add_argument("--prod", action="store_true", help="Use production (default: OT&E test environment)")
    args = parser.parse_args()

    if not args.remove and not args.geofeed:
        parser.error("--geofeed is required unless --remove is specified")
    if args.remove and args.geofeed:
        parser.error("--remove and --geofeed are mutually exclusive")
    if args.remove and args.update:
        parser.error("--remove and --update are mutually exclusive")

    api_key = get_api_key()
    base_url = PROD_BASE if args.prod else OTE_BASE
    env = "PRODUCTION" if args.prod else "OT&E (test)"

    print(f"Environment : {env}")
    print(f"Org handle  : {args.org}")
    if args.geofeed:
        print(f"Geofeed URL : {args.geofeed}")
    print(f"Mode        : {'remove' if args.remove else 'add' + (' + update' if args.update else '')}")
    print(f"Root only   : {args.root_only}")
    print(f"Dry run     : {args.dry_run}")
    print()

    if args.prod and not args.dry_run:
        confirm = input("WARNING: You are about to modify PRODUCTION records. Type 'yes' to continue: ")
        if confirm.strip().lower() != "yes":
            print("Aborted.")
            sys.exit(0)

    print(f"Fetching net handles for org {args.org}...")
    handles = get_org_net_handles(args.org)
    print(f"  Found {len(handles)} net records\n")

    updated = skipped = errors = 0

    for handle in handles:
        print(f"  {handle}", end=" ... ", flush=True)
        try:
            xml_str = get_net_record(base_url, handle, api_key)
        except Exception as e:
            print(f"ERROR fetching: {e}")
            errors += 1
            continue

        # --root-only: skip sub-allocations
        if args.root_only:
            if not is_root_record(xml_str, args.org, base_url, api_key):
                print("SKIP (sub-allocation, not root)")
                skipped += 1
                continue
            print("(root) ", end="", flush=True)

        existing = has_geofeed(xml_str)

        # --remove mode
        if args.remove:
            if not existing:
                print("SKIP (no Geofeed remark)")
                skipped += 1
                continue
            if args.dry_run:
                print(f"WOULD REMOVE ({existing})")
                updated += 1
                continue
            new_xml = build_removed_xml(xml_str)
            result, error = put_net_record(base_url, handle, api_key, new_xml)
            if error:
                print(f"ERROR: {error[:120]}")
                errors += 1
            else:
                print(f"REMOVED ({existing})")
                updated += 1
            continue

        # add/update mode
        if existing:
            if existing == f"Geofeed {args.geofeed}":
                print("SKIP (already correct)")
                skipped += 1
            elif args.update:
                if args.dry_run:
                    print(f"WOULD UPDATE ({existing} -> Geofeed {args.geofeed})")
                    updated += 1
                else:
                    new_xml = build_replaced_xml(xml_str, args.geofeed)
                    result, error = put_net_record(base_url, handle, api_key, new_xml)
                    if error:
                        print(f"ERROR: {error[:120]}")
                        errors += 1
                    else:
                        print(f"UPDATED ({existing} -> Geofeed {args.geofeed})")
                        updated += 1
            else:
                print(f"SKIP (has different URL: {existing}) — use --update to replace")
                skipped += 1
        else:
            if args.dry_run:
                print("WOULD ADD geofeed remark")
                updated += 1
            else:
                new_xml = build_added_xml(xml_str, args.geofeed)
                result, error = put_net_record(base_url, handle, api_key, new_xml)
                if error:
                    print(f"ERROR: {error[:120]}")
                    errors += 1
                else:
                    print("UPDATED")
                    updated += 1

    print()
    action = "removed" if args.remove else "updated"
    print(f"Results: {updated} {'would be ' if args.dry_run else ''}{action}, {skipped} skipped, {errors} errors")


if __name__ == "__main__":
    main()
