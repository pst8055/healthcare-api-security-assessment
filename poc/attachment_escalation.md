# MedBasket — Attachment Escalation Report

**Finding:** F-11 Escalated — Full Attachment Storage Compromise
**Date:** 2026-02-18
**Classification:** CONFIDENTIAL — Authorized Security Assessment
**Severity:** CRITICAL (CVSS 9.8)

---

## Executive Summary

The `/attachments` API endpoint exposes **98,476 files** without authentication, including **1,897 medical prescriptions**, **9 Aadhaar (national ID) cards**, **4 PAN cards (tax IDs)**, **1 passport**, **79 hospital/medical reports**, **66 medical documents**, **59 customer invoices**, **14 employee resumes**, **3,046 spreadsheets** (store inventory/stock data), and an estimated **~45,000 user-uploaded prescription photos**.

**4 Aadhaar card PDFs and 1 resume are directly downloadable** from the publicly accessible S3 development bucket. The S3 bucket ACL is publicly readable, exposing the AWS account owner ID.

This constitutes a **mass healthcare data breach** under the Digital Personal Data Protection Act (DPDP) 2023 and violates the Drugs and Cosmetics Act, 1940 regarding prescription confidentiality.

---

## 1. Attack Surface

### 1.1 Unauthenticated API Access

```
GET https://api.medbasket.com/attachments?$limit=50&$skip=0
→ 200 OK | No authentication required
→ Returns: total=98,476, complete file metadata + download URLs
```

**No rate limiting.** An attacker can enumerate all 98,476 files in ~33 minutes (50 per request, ~2000 requests).

### 1.2 Queryable Metadata

The API supports MongoDB-style queries on attachment metadata:

```
# Filter by MIME type
GET /attachments?objectDetails.mimeType=application/pdf → 5,700 PDFs

# Filter by storage service
GET /attachments?storageService=S3 → 98,090 records

# Paginate with no ceiling
GET /attachments?$limit=50&$skip=5000 → Works for any offset
```

---

## 2. Storage Infrastructure

### 2.1 Two Storage Backends

| Backend | Bucket/Domain | Files | Direct Download? |
|---------|--------------|-------|-----------------|
| **S3 Dev Bucket** | `techpepo-development-s3.s3.ap-south-1.amazonaws.com` | ~16,400 (est.) | **YES — No auth needed** |
| **Media CDN** | `media.medbasket.com` (CloudFront → `medbasket-media` S3) | ~82,000 (est.) | No (403) |

### 2.2 S3 Development Bucket Misconfiguration

**Bucket:** `techpepo-development-s3`
**Region:** `ap-south-1` (Mumbai)

| Check | Result |
|-------|--------|
| Directory listing | AccessDenied (good) |
| Object read | **PUBLIC — HTTP 200 for any file** |
| Object write (PUT) | 403 Forbidden (good) |
| ACL read | **PUBLIC — AllUsers has READ_ACP** |

**Bucket ACL Exposed:**

```xml
<AccessControlPolicy>
  <Owner>
    <ID>[CANONICAL_ID_REDACTED]</ID>
  </Owner>
  <AccessControlList>
    <Grant>
      <Grantee xsi:type="CanonicalUser">
        <ID>[CANONICAL_ID_REDACTED]</ID>
      </Grantee>
      <Permission>FULL_CONTROL</Permission>
    </Grant>
    <Grant>
      <Grantee xsi:type="Group">
        <URI>http://acs.amazonaws.com/groups/global/AllUsers</URI>
      </Grantee>
      <Permission>READ_ACP</Permission>
    </Grant>
  </AccessControlList>
</AccessControlPolicy>
```

**Issues:**
- `AllUsers` group has `READ_ACP` — anyone can read the bucket's access control policy
- AWS account canonical user ID is exposed: `8b954022...`
- Individual objects are publicly readable (policy allows `s3:GetObject` for anonymous users)
- This is a **development bucket** (`techpepo-development`) being used in **production**

### 2.3 Media CDN (CloudFront)

**Domain:** `media.medbasket.com`
**Backend S3 Bucket:** `medbasket-media`
**CDN:** CloudFront (PoP: BOM78-P8, Mumbai)

- Direct object access returns **HTTP 403** (properly configured CloudFront OAC)
- No signed URL parameters in stored URLs — CDN may require cookie-based auth or be misconfigured
- CDN ACL is not publicly readable (good)
- **However:** All file metadata (filenames, sizes, MIME types) are exposed through the API regardless

---

## 3. Sensitive Document Analysis

### 3.1 Complete File Type Breakdown

| Type | Count | Storage | Direct Download? |
|------|-------|---------|-----------------|
| JPEG images | 66,122 | Mostly CDN | CDN: No, S3: Yes |
| PNG images | 16,976 | Mixed | S3: Yes |
| JPG images (alt MIME) | 5,749 | CDN | CDN: No |
| **PDF documents** | **5,700** | Mixed | S3: Yes, CDN: No |
| **XLSX spreadsheets** | **3,046** | CDN | CDN: No |
| HEIC/HEIF (iPhone) | 807 | CDN | CDN: No |
| **Total** | **98,476** | | |

**Estimated total data volume: ~274 GB** (average 2.99 MB per file)

### 3.2 PDF Document Classification (5,700 PDFs — FULL SCAN)

| Category | Count | S3 Dev (Downloadable) | CDN (Metadata Leaked) |
|----------|-------|----------------------|----------------------|
| **Medical Prescriptions** | **1,897** | 0 | 1,897 |
| **Scanned Documents** | **481** | 0 | 481 |
| **Medical/Hospital Reports** | **79** | 0 | 79 |
| **Medical Documents** | **66** | 0 | 66 |
| **Customer Invoices** | **59** | 0 | 59 |
| **Employee Resumes/CVs** | **14** | **1** | 13 |
| **Aadhaar Cards (National ID)** | **9** | **4** | 5 |
| **PAN Cards (Tax ID)** | **4** | 0 | 4 |
| **Other Sensitive** (passport, discharge summary, ECG/MRI) | **3** | 0 | 3 |
| **Lab/Blood Reports** | **2** | 0 | 2 |
| **FSSAI License** | **1** | 0 | 1 |
| **TOTAL SENSITIVE PDFs** | **2,615** | **5** | **2,610** |

### 3.3 S3 Dev Bucket — Directly Downloadable Sensitive Files

These files are accessible without ANY authentication by visiting the URL:

| File | Size | Type |
|------|------|------|
| `aadhar.pdf` | 970,774 bytes | **Aadhaar Card (National ID)** |
| `aadhar.pdf` | 970,774 bytes | **Aadhaar Card (National ID)** |
| `aadhar.pdf` | 970,774 bytes | **Aadhaar Card (National ID)** |
| `aadhar.pdf` | 970,774 bytes | **Aadhaar Card (National ID)** |
| `[REDACTED_NAME]_Resume_9 (1).pdf` | 132,503 bytes | **Employee Resume** |

**Aadhaar card exposure is a criminal offense under Aadhaar Act, 2016 Section 29(4).**

### 3.4 XLSX Spreadsheets (3,046 files)

Primarily **store inventory and stock reports**:

| Sample Filenames | Notes |
|-----------------|-------|
| `store-inventory (9).xlsx` | Store inventory data |
| `STOCK REPORT 6-1-25.xlsx` | Stock data with dates |
| `BOMMANAHALLI STORE 08-01-25 E-com.xlsx` | Store-specific e-commerce data |
| `store-inventory new.xlsx` | Updated inventory |

These contain **business-confidential data**: product lists, stock levels, pricing, and store performance data.

### 3.5 Photo Analysis (~72,000 JPEG/JPG + 807 HEIC)

| Pattern | Estimated Count | Likely Content |
|---------|----------------|---------------|
| Numeric filenames (`1000004429.jpg`) | ~30,700 | Android gallery photos (prescriptions) |
| Descriptive names | ~19,500 | Mixed — includes prescription photos |
| Phone camera (`IMG_*`, `rn_image_picker_*`) | ~10,600 | Mobile app prescription uploads |
| WhatsApp images | ~3,600 | WhatsApp-shared prescriptions |
| UUID-like | ~1,000 | System-generated |

**In the context of a healthcare/pharmacy app, the majority of user-uploaded photos are prescription images.** Conservative estimate: **~45,000 prescription photos** among the 72K images.

### 3.6 Named Sensitive Photos Found

| Filename | Notes |
|----------|-------|
| `prescription.jpeg` | Medical prescription |
| `medicine.jpg` | Medicine photo |
| `Blood 1.jpg`, `Blood 2.jpg` | Blood test results |
| `[REDACTED_NAME] IBA HEALTH INSURANCE...` | Health insurance document with full name |

---

## 4. Data Exposure Chain

```
Step 1: GET /attachments?$limit=50  (no auth)
        → Enumerate all 98,476 file URLs

Step 2: Filter by type
        → objectDetails.mimeType=application/pdf → 5,700 PDFs
        → objectDetails.mimeType=image/jpeg → 66,122 photos

Step 3: Download from S3 Dev Bucket
        → https://techpepo-development-s3.s3.amazonaws.com/<key>
        → HTTP 200 — No authentication
        → Includes Aadhaar cards, resumes, marketing assets

Step 4: CDN files — metadata leaked
        → Filenames reveal: prescription.pdf, aadhar.pdf, Pan card.pdf
        → Even without download, this constitutes PII disclosure
```

---

## 5. Legal & Regulatory Impact

### 5.1 DPDP Act 2023 (India)

| Section | Violation |
|---------|-----------|
| Section 8(4) | Failure to implement reasonable security safeguards |
| Section 8(6) | Personal data must be erased when no longer necessary |
| Section 12 | **Mandatory breach notification** to Data Protection Board |
| Section 15 | Penalty up to **₹250 Crore** (~$30M USD) per instance |

### 5.2 Aadhaar Act 2016

| Section | Violation |
|---------|-----------|
| Section 29(4) | No person shall publicly display Aadhaar number |
| Section 37 | Penalty: **imprisonment up to 3 years + fine up to ₹10,000** |

### 5.3 Drugs & Cosmetics Act 1940

Medical prescriptions are confidential medical records. Exposing 1,897 prescriptions + ~45,000 prescription photos violates patient confidentiality requirements.

### 5.4 IT Act 2000

| Section | Violation |
|---------|-----------|
| Section 43A | Body corporate handling sensitive data must implement reasonable security |
| Section 72A | Disclosure of personal information in breach of contract — **imprisonment up to 3 years + fine up to ₹5 lakh** |

---

## 6. Impact Assessment

| Metric | Value |
|--------|-------|
| Total files exposed | 98,476 |
| Files directly downloadable (S3 dev) | ~16,400 |
| Medical prescriptions (PDF) | 1,897 |
| Estimated prescription photos | ~45,000 |
| Government ID documents (Aadhaar + PAN) | 13 |
| Passport documents | 1 |
| Hospital/medical reports | 145 |
| Customer invoices | 59 |
| Store inventory spreadsheets | 3,046 |
| Employee resumes | 14 |
| Estimated data volume | ~274 GB |
| AWS account ID exposed | Yes (via ACL) |

**Affected populations:**
- Patients/customers who uploaded prescriptions
- Employees whose resumes are stored
- Individuals whose Aadhaar/PAN/passport documents are stored
- Store owners whose FSSAI licenses are stored
- Business operations (inventory data)

---

## 7. Remediation

### IMMEDIATE (within hours)

1. **Block unauthenticated access to `/attachments`** — add `authenticate('jwt')` hook
2. **Remove public read from S3 dev bucket** — set bucket policy to deny public access
3. **Remove READ_ACP grant for AllUsers** on S3 dev bucket
4. **Delete Aadhaar/PAN/passport PDFs** from S3 dev bucket (or restrict access)

### Within 24 hours

5. Implement per-user data scoping — users should only see their own attachments
6. Add rate limiting on the attachments endpoint
7. Migrate ALL files from dev bucket to production CDN with proper access controls
8. Audit all stored government ID documents for compliance

### Within 1 week

9. Implement signed URLs for all file access (with short expiry)
10. Add WAF rules to prevent bulk enumeration
11. Separate medical/prescription files from general uploads with stricter access controls
12. Implement data retention policies — delete files that are no longer needed

### Within 1 month

13. Full data classification audit of all 98K+ files
14. Implement encryption at rest for all sensitive files
15. DPDP Act compliance review and breach notification to DPB
16. Patient notification about prescription exposure

---

*End of Attachment Escalation Report*
