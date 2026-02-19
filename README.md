# MedBasket API — Security Assessment

**Composite Risk Rating: 10.0 / 10.0 CRITICAL**

Full-scope API security assessment of a production healthcare/pharmacy platform serving 188,000+ users. Conducted as an authorized engagement.

---

## Scope

| Target | Stack | Scale |
|--------|-------|-------|
| `api.medbasket.com` | FeathersJS + MongoDB + AWS | 188K users, 63K orders, 6.6K medical records |
| `admin.medbasket.com` | Next.js + Auth.js v5 | Admin panel architecture |

## Key Findings (27 vulnerabilities)

| # | Finding | CVSS | OWASP |
|---|---------|------|-------|
| F-01 | Unauthenticated access to 188K user records (PII, OTPs, reset tokens) | 9.8 | API1 + API2 |
| F-02 | Password hash exposure via PATCH (Mongoose serialization bypass) | 9.8 | API3 |
| F-03 | Full account takeover chain via OTP leak — 4 steps, <3 seconds | 10.0 | API2 |
| F-04 | Admin account takeover via same OTP chain | 10.0 | API2 |
| F-05 | 63K orders accessible to any authenticated user (no RBAC) | 9.8 | API5 |
| F-06 | Live admin dashboard (revenue, customers) — no role check | 9.8 | API5 |
| F-07 | 6,655 medical records + prescription files exposed | 7.5 | API1 |
| F-08 | Swagger/OpenAPI spec publicly exposed (300+ endpoints) | 7.5 | API8 |
| F-09 | Unauthenticated database writes (PATCH, POST) | 8.6 | API2 |
| F-10 | Payment webhook abuse (PayU/Razorpay — no signature verification) | 8.1 | API8 |
| F-11 | 98K S3 files publicly accessible (Aadhaar cards, prescriptions) | 9.8 | API8 |
| F-12 | Schema disclosure via validation errors (27 fields) | 5.3 | API3 |
| F-13 | JWT misconfiguration (30-day lifetime, default audience, HS256) | 7.1 | API2 |
| F-14 | Admin panel = false security perimeter (UI-only auth) | 9.8 | API5 |
| F-15 | Super-admin endpoints accessible without authentication | 5.3 | API2 |

## Proven Kill Chain

```
Internet --> No Auth --> /users (188K PII records)
                    --> /users/request-otp (trigger SMS)
                    --> /users (read OTP from API response)
                    --> /authentication (get JWT -- 30-day validity)
                    --> /super-admin-users/orders (63K orders + GPS coordinates)
                    --> /dashboard (live revenue + customer PII)
                    --> /medicine-requests (6.6K medical records)
```

**Every step verified end-to-end on production. Time to full admin compromise: < 3 seconds.**

## Methodology

- OWASP API Security Top 10 (2023) + OWASP Web Application Top 10 (2021)
- CVSS v3.1 scoring
- Manual endpoint enumeration via Swagger + validation error probing
- Schema reconstruction from validation errors and Mongoose internals
- Privilege escalation testing (regular user to admin data access)
- Full data extraction capability demonstrated (pagination, no rate limiting)

## Deliverables

| File | Description |
|------|-------------|
| [`medbasket_security_assessment.md`](medbasket_security_assessment.md) | Full technical report — 760 lines, 27 findings, CVSS scores, remediation |
| [`poc/findings_evidence.md`](poc/findings_evidence.md) | Evidence package with redacted API responses (F-01 to F-15) |
| [`poc/walkthrough.md`](poc/walkthrough.md) | Client presentation script (75-90 minute meeting format) |
| [`poc/database_schema_map.md`](poc/database_schema_map.md) | Reconstructed database schema — 93 services, 567 endpoints |
| [`poc/attachment_escalation.md`](poc/attachment_escalation.md) | S3 bucket analysis — 98K files, Aadhaar/prescription exposure |
| [`poc/poc_medbasket.sh`](poc/poc_medbasket.sh) | Interactive PoC script (6-phase live demo) |
| [`poc/fetch_users.py`](poc/fetch_users.py) | Data extraction PoC — pagination with no rate limiting |
| [`poc/fetch_orders.py`](poc/fetch_orders.py) | Order extraction PoC — demonstrates BFLA |
| [`poc/build_dashboard.py`](poc/build_dashboard.py) | Automated dashboard builder from live API data |

## Regulatory Impact Assessed

- **DPDP Act 2023** (India) — up to INR 250 crore penalty
- **Aadhaar Act 2016** — criminal offense for public display of Aadhaar
- **IT Act 2000 Section 43A** — liability for inadequate data protection
- **GDPR** (if EU users present) — up to 4% global turnover

## Anonymization Notice

The company name, domain names, and all URLs in this repository have been anonymized. **"MedBasket" is a codename** — it does not represent a real company or domain. All URLs (e.g., `api.medbasket.com`) are fictitious and will not resolve. The actual target name was disclosed only to the client under NDA.

All personally identifiable information has also been redacted. Real emails, phone numbers, names, credentials, tokens, hashes, addresses, and GPS coordinates have been replaced with placeholders. Original unredacted findings were delivered to the client.

---

> **Disclaimer:** This assessment was conducted with explicit written authorization. See [DISCLAIMER.md](DISCLAIMER.md) for full legal notice. Reproducing these techniques against any system without authorization is illegal.
