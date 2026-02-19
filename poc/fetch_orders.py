#!/usr/bin/env python3
"""Fetch ALL orders from MedBasket API — standalone script."""

import urllib.request
import json
import ssl
import csv
import os
import sys
import time

API = "https://api.medbasket.com"
TOKEN = "<TOKEN_REDACTED>"
ENDPOINT = "/super-admin-users/orders"
BATCH = 50
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
ctx = ssl.create_default_context()


def fetch(path):
    url = API + path
    for attempt in range(3):
        try:
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"Bearer {TOKEN}")
            req.add_header("Accept", "application/json")
            with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
                return json.loads(resp.read())
        except Exception as ex:
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
            else:
                raise


def flatten(obj, prefix=""):
    out = {}
    if not isinstance(obj, dict):
        return {prefix: obj}
    for k, v in obj.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.update(flatten(v, key))
        elif isinstance(v, list):
            out[key] = json.dumps(v)
        else:
            out[key] = v
    return out


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    print("Fetching orders from api.medbasket.com ...")
    first = fetch(f"{ENDPOINT}?$limit={BATCH}&$skip=0")
    total = first.get("total", 0)
    records = first.get("data", [])
    print(f"Total: {total:,}")

    while len(records) < total:
        pct = int(len(records) / total * 100)
        print(f"\r  [{pct:3d}%] {len(records):,} / {total:,}", end="", flush=True)
        batch = fetch(f"{ENDPOINT}?$limit={BATCH}&$skip={len(records)}")
        data = batch.get("data", [])
        if not data:
            break
        records.extend(data)
        time.sleep(0.1)

    print(f"\r  [100%] {len(records):,} / {total:,}")

    # Save JSON
    json_path = os.path.join(OUT_DIR, "orders.json")
    with open(json_path, "w") as f:
        json.dump({"total": total, "fetched": len(records), "data": records}, f)
    print(f"JSON: {json_path} ({os.path.getsize(json_path)/1048576:.1f} MB)")

    # Save CSV
    csv_path = os.path.join(OUT_DIR, "orders.csv")
    all_keys = set()
    flat = []
    for r in records:
        fr = flatten(r)
        flat.append(fr)
        all_keys.update(fr.keys())
    keys = sorted(all_keys)
    if "_id" in keys:
        keys.remove("_id")
        keys.insert(0, "_id")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(flat)
    print(f"CSV:  {csv_path} ({os.path.getsize(csv_path)/1048576:.1f} MB)")

    print(f"Done — {len(records):,} orders saved.")


if __name__ == "__main__":
    main()
