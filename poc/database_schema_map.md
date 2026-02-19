# MedBasket — Database Schema Map & Attack Surface Enumeration

**Date:** 2026-02-18
**Classification:** CONFIDENTIAL — Authorized Security Assessment
**Methodology:** Schema inference via validation errors, $select probing, Mongoose internals, Swagger/OpenAPI, and response analysis

---

## Executive Summary

Through systematic probing of the MedBasket API (`api.medbasket.com`), we reconstructed the majority of the application's database schema **without any source code access**. The API is built on **FeathersJS + MongoDB (Mongoose)** and exposes schema information through multiple channels:

| Technique | Data Recovered |
|-----------|---------------|
| `$select[]=__INVALID__` validation errors | Field lists for 10+ collections |
| POST empty `{}` validation chaining | Required fields for 6+ services |
| GET response analysis | Full nested schemas for orders, users, addresses, stores |
| Mongoose `_doc` / `$__` internal leak | Raw document internals on `/users` |
| Swagger/OpenAPI (`/swagger.json`) | 272 paths, 93 services, 567 methods |

**Critical finding:** 563 of 567 endpoint methods have **no security definition** in Swagger. Only 4 methods define any security requirement.

---

## 1. API Surface Overview (from Swagger)

### 1.1 Statistics

| Metric | Value |
|--------|-------|
| Total API paths | 272 |
| Total services | 93 |
| Total endpoint methods (GET/POST/PATCH/PUT/DELETE) | 567 |
| Methods with security defined | 4 (0.7%) |
| Methods without security defined | 563 (99.3%) |
| Swagger schema definitions | 0 (empty!) |

### 1.2 Complete Service Inventory (93 services)

| # | Service | Methods | Auth Required? |
|---|---------|---------|---------------|
| 1 | `admin` | GET, POST, PATCH, DELETE | JWT (admin) |
| 2 | `admin-zip-codes` | GET, POST, PATCH, DELETE | Partial |
| 3 | `analytics-tracker-history` | POST, PATCH | None defined |
| 4 | `app-data` | GET, POST, PATCH, DELETE | None (open) |
| 5 | `app-install-referrer-tracker` | POST | None defined |
| 6 | `app-logs` | GET, POST, PATCH, DELETE | None defined |
| 7 | `application-tax` | GET, POST, PATCH, DELETE | None (open read) |
| 8 | `apply-coupon` | GET, POST | JWT |
| 9 | `attachments` | GET, POST, PATCH, DELETE | None (open read!) |
| 10 | `bulk-upload` | GET, POST, PATCH, DELETE | JWT (admin) |
| 11 | `bulk-upload-process` | GET, POST, PATCH, DELETE | JWT (admin) |
| 12 | `carts` | GET, POST, PATCH, DELETE | JWT |
| 13 | `categories` | GET, POST, PATCH, DELETE | JWT (admin) |
| 14 | `chatgpt-product-info-generation` | GET, POST, PATCH, DELETE | None defined |
| 15 | `chatgpt-translation` | GET, POST, PATCH, DELETE | None defined |
| 16 | `check-stock-availability` | POST | None defined |
| 17 | `checkout-session-failed-order` | GET, POST, PATCH, DELETE | None defined |
| 18 | `collections` | GET, POST, PATCH, DELETE | JWT (admin) |
| 19 | `consultancy-appointment-slots` | GET, POST, PATCH, DELETE | None (open read) |
| 20 | `consultation-items` | GET | JWT |
| 21 | `consultations` | GET, POST, PATCH, DELETE | JWT |
| 22 | `consumer` | GET | None (open) |
| 23 | `consumer-ticket` | GET, POST, PATCH, DELETE | JWT |
| 24 | `contact-us` | GET, POST, PATCH, DELETE | None (open!) |
| 25 | `coupon-usages` | GET, POST | JWT |
| 26 | `coupons` | GET, POST, PATCH, DELETE | JWT (admin) |
| 27 | `create-ticket-from-admin` | POST, PATCH | JWT (admin) |
| 28 | `dashboard` | GET | JWT (admin) |
| 29 | `reward-coins-history` | GET, POST, PATCH, DELETE | JWT |
| 30 | `delivery-mode-templates` | GET | None defined |
| 31 | `delivery-policies` | GET, POST, PATCH, DELETE | JWT (admin) |
| 32 | `download-excel` | GET, POST, PATCH, DELETE | JWT (admin) |
| 33 | `downloads` | GET, POST, PATCH, DELETE | JWT |
| 34 | `export-jobs` | POST | JWT (admin) |
| 35 | `exports` | POST | JWT (admin) |
| 36 | `fetch-stores-post` | POST | None defined |
| 37 | `fetch-zip-codes-post` | POST | None defined |
| 38 | `file-transfer` | GET, POST, PATCH, DELETE | None defined |
| 39 | `general` | GET, POST | None (open) |
| 40 | `global-search` | GET, POST, DELETE | None defined |
| 41 | `i18n-settings` | GET, POST, PATCH, DELETE | None defined |
| 42 | `inventory-stock` | GET | JWT (admin) |
| 43 | `logistics` | GET, POST, PATCH, DELETE | JWT (admin) |
| 44 | `medicine-remainder` | GET, POST, PATCH, DELETE | JWT |
| 45 | `medicine-requests` | GET, POST, PATCH, DELETE | JWT |
| 46 | `membership-orders` | GET, POST, PATCH, DELETE | JWT |
| 47 | `memberships` | GET, POST, PATCH, DELETE | JWT |
| 48 | `modules` | GET, POST, PATCH, DELETE | JWT (admin) |
| 49 | `navigations` | GET, POST, PATCH, DELETE | JWT (admin) |
| 50 | `notifications` | GET, POST, PATCH, DELETE | JWT |
| 51 | `order` | GET, POST, PATCH, DELETE | JWT |
| 52 | `order-item-tracking` | GET, POST, PATCH, DELETE | JWT |
| 53 | `patients` | GET, POST, PATCH, DELETE | JWT |
| 54 | `payment` | GET, POST, PATCH, DELETE | Partial (open POST!) |
| 55 | `permissions` | GET, POST, PATCH, DELETE | JWT (admin) |
| 56 | `policies` | GET, POST, PATCH, DELETE | None (open read) |
| 57 | `policies-user` | GET, POST, PATCH, DELETE | JWT |
| 58 | `prescription-status` | GET, POST, PATCH, DELETE | JWT |
| 59 | `product` | GET | None (open) |
| 60 | `product-bulk-upload` | POST | JWT (admin) |
| 61 | `products` | GET | None (open) |
| 62 | `referral-credits` | GET, POST, PATCH, DELETE | JWT |
| 63 | `reports` | POST | JWT (admin) |
| 64 | `request-super-admin-otp` | POST | JWT (admin) |
| 65 | `resend-store-invite` | GET, POST, PATCH, DELETE | JWT (admin) |
| 66 | `roles` | GET, POST, PATCH, DELETE | JWT (admin) |
| 67 | `sales` | GET, POST, PATCH, DELETE | JWT (admin) |
| 68 | `settings` | GET, POST, PATCH, DELETE | JWT (admin) |
| 69 | `sponsored` | GET, POST, PATCH, DELETE | JWT (admin) |
| 70 | `sponsored-banners` | GET, POST, PATCH, DELETE | JWT (admin) |
| 71 | `sponsored-layout` | GET | None (open) |
| 72 | `store` | GET, POST, PATCH, DELETE | JWT (store admin) |
| 73 | `store-admin` | GET, POST, PATCH, DELETE | JWT (store admin) |
| 74 | `store-admin-users` | GET, POST, PATCH, DELETE | JWT (store admin) |
| 75 | `store-inventory` | GET, POST, PATCH, PUT, DELETE | JWT (store admin) |
| 76 | `store-pharmacist` | GET, POST, PATCH, DELETE | JWT (store admin) |
| 77 | `store-settings` | GET, POST, PATCH, DELETE | JWT (store admin) |
| 78 | `stores` | GET, POST, PATCH, DELETE | JWT (admin) |
| 79 | `super-admin` | GET, POST, PATCH, DELETE | JWT (super admin) |
| 80 | `super-admin-users` | GET, POST, PATCH, PUT, DELETE | JWT (super admin) |
| 81 | `support` | GET, POST, PATCH, DELETE | JWT |
| 82 | `taxes` | GET, POST, PATCH, DELETE | JWT (admin) |
| 83 | `tickets` | GET, POST, PATCH | JWT |
| 84 | `upload-invoice` | GET, POST, PATCH, DELETE | JWT |
| 85 | `user-addresses` | GET, POST, PATCH, DELETE | JWT |
| 86 | `user-invitations` | GET, POST, PATCH, DELETE | JWT (admin) |
| 87 | `users` | GET, POST, PATCH, DELETE | None (open!) |
| 88 | `verify-payment` | POST | None defined |
| 89 | `verify-phone-otp` | POST | None defined |
| 90 | `version-update` | GET, POST | None (open) |
| 91 | `webhooks` | GET, POST, PATCH, DELETE | None defined |
| 92 | `zip-codes` | GET, POST, PATCH, DELETE | None (open read) |
| 93 | `zip-codes-get` | GET | None (open) |

---

## 2. Reconstructed Database Schemas

### 2.1 Users Collection — `users`

**Total Records:** ~188,000
**Access:** Unauthenticated (full CRUD!)
**Disclosure Method:** `$select[]=__INVALID__` + GET response + Mongoose `_doc` leak

#### Fields (26 from $select validation):

| # | Field | Type | Sensitivity | Sample / Notes |
|---|-------|------|------------|----------------|
| 1 | `_id` | ObjectId | Low | `6000000000000000000000a1` |
| 2 | `email` | String | **HIGH** | `admin@[REDACTED].com` |
| 3 | `phoneNumber` | String | **HIGH** | `+91XXXXXXXXXX` |
| 4 | `password` | String | **CRITICAL** | Bcrypt hash (filtered from $select but exists) |
| 5 | `googleId` | String | HIGH | OAuth identifier |
| 6 | `accountVerified` | Boolean | Medium | `true` |
| 7 | `tempPhoneNumber` | String | HIGH | Temp number during change |
| 8 | `phoneOtp` | String | **CRITICAL** | OTP for auth — **exposed in GET!** |
| 9 | `phoneOtpValidTill` | String | **CRITICAL** | OTP expiry — enables takeover |
| 10 | `passwordResetToken` | String | **CRITICAL** | Reset token — **exposed in GET!** |
| 11 | `passwordResetTokenExpiry` | String | **CRITICAL** | Token expiry |
| 12 | `dateOfBirth` | String | HIGH | `1990-01-01T00:00:00.000Z` |
| 13 | `gender` | String | Medium | `male` |
| 14 | `height` | Number | Medium | Health data |
| 15 | `weight` | Number | Medium | Health data |
| 16 | `createdAt` | String | Low | `2024-10-26T10:53:34.000Z` |
| 17 | `updatedAt` | String | Low | Auto-managed |
| 18 | `hasPremiumMembership` | Boolean | Low | `false` |
| 19 | `rewardCoinsBalance` | Number | Medium | `0` |
| 20 | `premiumMembership` | Object | Medium | Membership details |
| 21 | `profileToken` | String | **CRITICAL** | Session/profile token |
| 22 | `profileTokenValidTill` | String | HIGH | Token expiry |
| 23 | `identifierType` | String | Low | `mobile` |
| 24 | `isWeb` | Boolean | Low | Platform flag |
| 25 | `referralCode` | String | Low | Referral tracking |
| 26 | `referral` | Object | Low | Referral details |

**Additional fields from GET response (not in $select list):**
- `name` (String) — Full name
- `phone` (String) — Secondary phone

**CRITICAL:** The `phoneOtp`, `passwordResetToken`, `profileToken` fields are **returned in unauthenticated GET** requests. This enables account takeover for any user.

---

### 2.2 Orders Collection — `super-admin-users/orders`

**Total Records:** ~63,000
**Access:** Requires JWT (obtainable via OTP leak from users endpoint)
**Disclosure Method:** GET response analysis

#### Fields (108 total including nested objects):

**Top-level Order Fields:**

| # | Field | Type | Notes |
|---|-------|------|-------|
| 1 | `_id` | ObjectId | Order document ID |
| 2 | `orderId` | String | Human-readable order ID (`0XXXXXXXX`) |
| 3 | `status` | String | `paid`, `delivered`, `cancelled`, etc. |
| 4 | `orderTotal` | Number | `166.5` |
| 5 | `subTotal` | Number | `112.5` |
| 6 | `currency` | String | `INR` |
| 7 | `addressId` | ObjectId | Reference to user-addresses |
| 8 | `couponCode` | String/null | Applied coupon |
| 9 | `offerId` | String/null | Applied offer |
| 10 | `discountedAmount` | Number | `0` |
| 11 | `deliveryCharge` | Number | `49` |
| 12 | `paymentAmount` | Number | `166.5` |
| 13 | `taxAmount` | Number | `5.63` |
| 14 | `paymentMode` | String | `payu` |
| 15 | `paymentOrderId` | String | `TXN[REDACTED]` |
| 16 | `hasPrescription` | Boolean | `false` |
| 17 | `consultDoctorForPrescription` | Boolean | `false` |
| 18 | `handlingCharge` | Number | `0` |
| 19 | `packingCharge` | Number | `0` |
| 20 | `platformFee` | Number | `5` |
| 21 | `deliveryMode` | String | `oneDay` |
| 22 | `patientId` | ObjectId | Patient reference |
| 23 | `hasMembershipFreeDeliveryBenefit` | Boolean | `false` |
| 24 | `deviceType` | String | `android` |
| 25 | `isRewardCoinsApplied` | Boolean | `false` |
| 26 | `rewardCoinsUsed` | Number | `0` |
| 27 | `premiumMembershipAmount` | Number | `0` |
| 28 | `isPremiumMembershipAdded` | Boolean | `false` |
| 29 | `utmParams` | Object/null | UTM tracking |
| 30 | `lastTimelineStatus` | String | `Order Under Verification` |
| 31 | `createdAt` | String | Timestamp |
| 32 | `updatedAt` | String | Timestamp |
| 33 | `__v` | Number | Mongoose version key |

**Nested: `prescription` Object:**

| Field | Type |
|-------|------|
| `prescription.urls` | Array |

**Nested: `items[]` Array:**

| Field | Type | Notes |
|-------|------|-------|
| `items[].productId` | ObjectId | Product reference |
| `items[].quantity` | Number | `1` |
| `items[].amount` | Number | `112.5` |
| `items[].total` | Number | `112.5` |
| `items[]._id` | ObjectId | Line item ID |

**Nested: `address` Object (17 fields) — FULL USER ADDRESS POPULATED:**

| Field | Type | Sample |
|-------|------|--------|
| `address._id` | ObjectId | |
| `address.userName` | String | `[REDACTED_NAME]` |
| `address.phoneNumber` | String | `XXXXXXXXXX` |
| `address.addressLine1` | String | `[REDACTED_ADDRESS]` |
| `address.addressLine2` | String | `[REDACTED_AREA]` |
| `address.postalCode` | String | `XXXXXX` |
| `address.city` | String | `KOLKATA` |
| `address.state` | String | `WEST BENGAL` |
| `address.isDefault` | Boolean | |
| `address.type` | String | |
| `address.coordinates.longitude` | Number | `XX.XXXXXX` |
| `address.coordinates.latitude` | Number | `XX.XXXXXX` |
| `address.fullAddress` | String | Full street address |
| `address.alternatePhoneNumber` | String | `XXXXXXXXXX` |
| `address.country` | String | `india` |
| `address.userId` | ObjectId | |
| `address.createdAt` | String | |
| `address.updatedAt` | String | |

**Nested: `store` Object (21+ fields) — FULL STORE DATA POPULATED:**

| Field | Type | Sample |
|-------|------|--------|
| `store._id` | ObjectId | |
| `store.storeCode` | String | `[STORE_CODE]` |
| `store.storeName` | String | Full store name + location |
| `store.gstNumber` | String | `[GST_REDACTED]` |
| `store.fssaiNumber` | String | `[FSSAI_REDACTED]` |
| `store.licenceNumber` | String | Drug licence |
| `store.email` | String | `store1@[REDACTED].com` |
| `store.phoneNumber` | String | `XXXXXXXXXX` |
| `store.address` | String | Full physical address |
| `store.city` | String | |
| `store.state` | String | |
| `store.pincode` | String | |
| `store.country` | String | |
| `store.serviceableZip` | Array | 1282 ZIP codes per store |
| `store.storeSettings.assignee` | Array | |
| `store.storeId` | String | |
| `store.active` | Boolean | |
| `store.acceptedInvitation` | Boolean | |
| `store.coordinates.longitude` | Number | |
| `store.coordinates.latitude` | Number | |
| `store.logistics.shiprocketQuick.pickupLocation` | String | |
| `store.logistics.delhivery.pickupLocation` | String | |

**Nested: `userId` Object (17 fields) — FULL USER DATA POPULATED:**

| Field | Type | Notes |
|-------|------|-------|
| `userId._id` | ObjectId | |
| `userId.email` | String | **PII** — `customer6@[REDACTED].com` |
| `userId.phoneNumber` | String | **PII** — `+91XXXXXXXXXX` |
| `userId.accountVerified` | Boolean | |
| `userId.phoneOtp` | null | OTP field (visible!) |
| `userId.phoneOtpValidTill` | null | |
| `userId.createdAt` | String | |
| `userId.updatedAt` | String | |
| `userId.hasPremiumMembership` | Boolean | |
| `userId.rewardCoinsBalance` | Number | |
| `userId.identifierType` | String | |
| `userId.__v` | Number | |
| `userId.profileToken` | String | (empty in sample) |
| `userId.profileTokenValidTill` | null | |
| `userId.dateOfBirth` | String | **PII** — DOB |
| `userId.gender` | String | **PII** |
| `userId.name` | String | **PII** — Full name |

---

### 2.3 Attachments Collection — `attachments`

**Total Records:** 98,464
**Access:** Unauthenticated
**Storage:** AWS S3 (`techpepo-development-s3.s3.ap-south-1.amazonaws.com`)

| # | Field | Type | Sample |
|---|-------|------|--------|
| 1 | `_id` | ObjectId | `6000000000000000000000b6` |
| 2 | `storageService` | String | `S3` |
| 3 | `objectDetails.size` | Number | `48100` |
| 4 | `objectDetails.fileName` | String | `6LxdkEbKhemH38c5s7dOs-bags.png` |
| 5 | `objectDetails.originalFileName` | String | `bags.png` |
| 6 | `objectDetails.mimeType` | String | `image/png` |
| 7 | `objectUrl` | String | Full S3 URL (publicly accessible) |

**Note:** This includes prescription images, medical documents, and store assets — all publicly enumerable and downloadable.

---

### 2.4 Zip Codes Collection — `zip-codes`

**Total Records:** 19,794
**Access:** Unauthenticated

| # | Field | Type | Sample |
|---|-------|------|--------|
| 1 | `_id` | ObjectId | |
| 2 | `area` | String | `Nanded` |
| 3 | `district` | String | `NANDED` |
| 4 | `state` | String | `MAHARASHTRA` |
| 5 | `zipCode` | String | `431601` |
| 6 | `location.type` | String | `Point` |
| 7 | `location.coordinates` | Array | `[XX.XXXXXX, XX.XXXXXX]` (GeoJSON) |
| 8 | `isDeliverable` | Boolean | `true` |

---

### 2.5 Admin Zip Codes — `admin-zip-codes`

**$select Fields (2):** `_id`, `text`

---

### 2.6 App Data Collection — `app-data`

**Access:** Unauthenticated
**$select Fields (7):**

| # | Field | Type |
|---|-------|------|
| 1 | `_id` | ObjectId |
| 2 | `name` | String |
| 3 | `visibility` | String |
| 4 | `type` | String |
| 5 | `description` | String |
| 6 | `imageUrl` | String |
| 7 | `value` | Mixed |

**Required for POST:** `name`, `type`

---

### 2.7 Application Tax — `application-tax`

**Access:** Unauthenticated
**$select Fields (4):** `_id`, `defaultTax`, `createdBy`, `updatedBy`

---

### 2.8 Consultancy Appointment Slots — `consultancy-appointment-slots`

**Access:** Unauthenticated
**$select Fields (7):**

| # | Field | Type |
|---|-------|------|
| 1 | `_id` | ObjectId |
| 2 | `date` | String |
| 3 | `startTime` | String |
| 4 | `endTime` | String |
| 5 | `maxAppointments` | Number |
| 6 | `appointments` | Array |
| 7 | `availableCount` | Number |

---

### 2.9 Policies Collection — `policies`

**Total Records:** 6
**Access:** Unauthenticated (returns raw array, no pagination wrapper)
**$select Fields (3):** `_id`, `name`, `content`

**Additional fields in response:** `type`, `value.url`, `value.version`, `value.lastUpdateAt`, `value.lastUpdateBy`

| Policy Name | Version |
|-------------|---------|
| `privacy_policy` | 13 |
| `terms_and_conditions` | 4 |
| `grevience_readdressal` | 6 |
| `shipping_and_delivery_policy` | 7 |
| `return_refund` | 3 |
| `ip_policy` | 5 |

---

### 2.10 Contact Us — `contact-us`

**Access:** Unauthenticated (read + write!)
**$select Fields (1):** `id`
**POST Required Fields (chained):** `name` → `email` → `phoneNumber` → `message`

---

### 2.11 Products — `products`

**Access:** Unauthenticated (read-only)
**$select Fields (8):** `id`, `category`, `sponsored`, `filter`, `page`, `limit`, `userId`, `cartSimilarProducts`

---

### 2.12 Patients Collection — `patients`

**Access:** JWT required
**Response format:** Raw array (no pagination wrapper)

**Fields from sample:**

| # | Field | Type |
|---|-------|------|
| 1 | `_id` | ObjectId |
| 2 | `name` | String |
| 3 | `phoneNumber` | String |
| 4 | `email` | String |
| 5 | `dateOfBirth` | String |
| 6 | `gender` | String |
| 7 | `relation` | String |
| 8 | `userId` | ObjectId |

---

## 3. POST Validation Disclosure — Required Field Chains

By sending empty `{}` POST requests and incrementally adding fields until the next required field is disclosed, we mapped:

| Service | Required Fields (in order) | Unauthenticated? |
|---------|---------------------------|-----------------|
| `contact-us` | name → email → phoneNumber → message | **YES** |
| `app-data` | name → type | **YES** |
| `payment` | (no validation — creates records!) | **YES — WRITE!** |
| `carts` | (requires JWT) | No |
| `consultations` | (requires JWT) | No |
| `memberships` | (requires JWT) | No |
| `patients` | (requires JWT) | No |

**CRITICAL:** `POST /payment` accepts requests **without authentication** and creates records. This is an unauthenticated write to a payment collection.

---

## 4. Mongoose Internals Leak

**Endpoint:** `PATCH /users/{id}` with empty body `{}`
**Effect:** Returns Mongoose document internals including:

- `$__` — Internal Mongoose state object
- `$isNew` — Document creation flag
- `_doc` — Raw MongoDB document with ALL fields including:
  - `password` (bcrypt hash)
  - `phoneOtp` (active OTP)
  - `passwordResetToken`
  - `profileToken`
  - All PII fields

This is unique to the `/users` endpoint — other endpoints return normal JSON errors.

---

## 5. Data Volume Summary

| Collection | Records | Unauthenticated Access |
|------------|---------|----------------------|
| Users | ~188,000 | **YES** (full CRUD) |
| Attachments | 98,464 | **YES** (read + S3 URLs) |
| Orders | ~63,000 | JWT required (obtainable via OTP leak) |
| Zip Codes | 19,794 | **YES** |
| Medicine Requests | ~6,600 | JWT required |
| Policies | 6 | **YES** |
| Appointment Slots | Variable | **YES** |

**Estimated total PII records at risk:** 250,000+

---

## 6. Authentication Bypass Chain

The following chain demonstrates how unauthenticated access escalates to full database access:

```
Step 1: GET /users?$limit=1
        → Returns user with phoneOtp, passwordResetToken

Step 2: POST /authentication
        → Use leaked phoneOtp to get JWT token

Step 3: GET /super-admin-users/orders?$limit=50&$skip=0
        → With JWT, paginate all 63,000 orders
        → Each order contains full user data, address, store info

Step 4: GET /medicine-requests, /user-addresses, /patients, etc.
        → With JWT, access all authenticated endpoints
```

---

## 7. Unauthenticated Data Exposure Summary

### Readable without any authentication:

| Endpoint | Records | Sensitive Data |
|----------|---------|---------------|
| `/users` | 188K | Email, phone, name, DOB, OTP, password reset tokens |
| `/attachments` | 98K | S3 URLs to prescriptions, medical docs |
| `/zip-codes` | 19K | Service area mapping with GPS coordinates |
| `/app-data` | Variable | App configuration, feature flags |
| `/application-tax` | Variable | Tax configuration |
| `/consultancy-appointment-slots` | Variable | Doctor appointment schedules |
| `/policies` | 6 | Company policies (low sensitivity) |
| `/contact-us` | Variable | Customer complaints with PII |
| `/products` | Variable | Product catalog |
| `/version-update` | 1 | App version info |

### Writable without any authentication:

| Endpoint | Method | Impact |
|----------|--------|--------|
| `/users` | POST, PATCH, DELETE | Create/modify/delete user accounts |
| `/contact-us` | POST | Inject fake support requests |
| `/payment` | POST | Create payment records |
| `/app-data` | POST | Inject app configuration |
| `/attachments` | POST | Upload files to S3 |

---

## 8. Sensitive Field Exposure Matrix

| Field Type | Endpoint | Count |
|-----------|----------|-------|
| Email addresses | `/users` | 188,000 |
| Phone numbers | `/users`, orders (nested) | 188,000+ |
| Physical addresses (with GPS) | Orders → `address` nested | 63,000 |
| Date of birth | `/users`, orders → `userId` nested | 188,000 |
| OTP codes | `/users` → `phoneOtp` | Active OTPs |
| Password reset tokens | `/users` → `passwordResetToken` | Active tokens |
| Password hashes | `/users` via PATCH `_doc` | 188,000 |
| Medical prescriptions | `/attachments` → S3 URLs | 98,464 files |
| Store GST/FSSAI/licence | Orders → `store` nested | All stores |
| Payment transaction IDs | Orders → `paymentOrderId` | 63,000 |
| Patient health data | `/patients` (via JWT) | Variable |

---

## 9. Store-Admin Attack Surface

### Discovered Bugs:

| Endpoint | Issue |
|----------|-------|
| `POST /store-admin-users/forgot-password` | Returns `Cannot read properties of undefined (reading 'toLowerCase')` |
| `POST /store-admin-users/reset-password` | Returns `Cannot read properties of undefined (reading 'toLowerCase')` |

These indicate broken error handling that may be exploitable.

### Admin-Gated Endpoints (return "No record found for id"):
These services look up the JWT user ID in the admin collection — regular user JWT fails:

`stores`, `categories`, `roles`, `permissions`, `settings`, `sales`, `collections`, `navigations`, `logistics`, `store-inventory`, `coupons`, `delivery-policies`, `modules`, `sponsored`, `sponsored-banners`

---

## 10. Swagger Gap Analysis

| Aspect | Expected | Actual |
|--------|----------|--------|
| Schema definitions | All models | **0 definitions** |
| Security definitions on endpoints | All 567 | **4 only** |
| Authentication documented | Yes | Minimal |
| Rate limiting documented | Yes | **None** |
| Input validation documented | Yes | **None** |

The Swagger documentation is effectively a path listing with zero security or schema information — useful for attackers to enumerate the API surface but provides no defensive value.

---

## 11. Remediation Priority

### IMMEDIATE (24-48 hours):
1. **Remove `phoneOtp`, `passwordResetToken`, `profileToken`, `password` from all API responses**
2. **Add authentication to `/users` GET endpoint** — currently returns 188K user records unauthenticated
3. **Add authentication to `/attachments` GET endpoint** — 98K files including prescriptions
4. **Disable unauthenticated POST to `/payment`**
5. **Remove Mongoose internals from PATCH responses** — disable `_doc` / `$__` leak

### HIGH (1 week):
6. Implement per-user data scoping (users can only see their own data)
7. Add rate limiting to all endpoints
8. Implement $limit ceiling (max 50 per page, server-enforced)
9. Remove nested population of sensitive user/store data in order responses
10. Fix store-admin-users forgot-password/reset-password error handling

### MEDIUM (1 month):
11. Add security definitions to all Swagger endpoints
12. Implement proper RBAC across all 93 services
13. Add schema definitions to Swagger
14. Audit all 567 endpoint methods for authorization
15. Implement field-level access control to prevent $select probing

---

*End of Database Schema Map*
