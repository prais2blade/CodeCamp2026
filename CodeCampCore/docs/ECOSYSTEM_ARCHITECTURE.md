# CodeCamp Ecosystem Architecture & SaaS Roadmap

## 1. Executive Summary & Purpose

The **CodeCamp Suite** consists of three decoupled, independently deployable systems that together form a comprehensive Academy Management & Attendance ecosystem, architected for eventual transformation into a multi-tenant SaaS platform:

```
                          ┌────────────────────────┐
                          │        Codecamp        │
                          │   (Admissions & Camp   │
                          │    Student Gateway)    │
                          └───────────┬────────────┘
                                      │
                         HTTP REST API (M2M Auth)
                         - Registration Sync
                         - Batch Allocation
                                      │
            ┌─────────────────────────┴─────────────────────────┐
            ▼                                                   ▼
┌───────────────────────┐                           ┌───────────────────────┐
│     CodeCampCore      │◄───── HTTP Attendance ────┤   attendance-system   │
│   (Master Academy     │          Sync API         │ (Daily Scanner, Kiosk │
│   ERP & Admin Portal) │                           │   & Guardian Alerts)  │
└───────────────────────┘                           └───────────────────────┘
```

---

## 2. System Responsibilities & Boundaries

### 🏛️ `CodeCampCore` (Master Academy ERP & Portal)
- **Role:** Central Source of Truth for the Academy.
- **Key Modules:**
  - **Academic Structure:** Courses, Batches, Terms, Schedules, Lessons, Curriculum.
  - **User & Identity Hub:** SuperAdmins, Academy Admins, Teachers, Students, Parents with granular RBAC permissions.
  - **Financials:** Invoicing, Payment Tracking, Course Fees, Receipts.
  - **Master Attendance Ledger:** Centralized attendance repository aggregating feeds from kiosk scanners and mobile apps.
  - **Integration Engine:** Ingestion endpoints (`/api/v1/enrollment/sync/`, `/api/v1/attendance/sync/`, `/api/v1/catalog/courses/`) authenticated via cryptographic API keys.

### 🎒 `Codecamp` (Admissions & Campaign Gateway)
- **Role:** High-conversion public portal for camp marketing and student sign-ups.
- **Key Modules:**
  - **Camp Landing Experience:** Course showcases, pricing calculator, early-bird limits.
  - **Registration Funnel:** Parent & child data capture, proof of payment receipt uploads.
  - **Batch Allocation Engine:** Automated capacity assignment with overflow waitlists.
  - **Outbound Dispatcher (`SyncDispatcher`):** Pushes approved registrations to both `attendance-system` (for QR badges) and `CodeCampCore` (for ERP student accounts).

### 📱 `attendance-system` (Scanner Station & Guardian Hub)
- **Role:** High-speed physical check-in kiosk and instant notification hub.
- **Key Modules:**
  - **QR Code Engine:** Real-time camera & handheld laser scanner check-in/check-out.
  - **Guardian Alerts:** Instant WhatsApp/SMS webhook dispatches on arrival/departure.
  - **Offline/Resilient Scanning:** Local verification with background batch sync to `CodeCampCore` via `CoreAttendanceSyncService`.

---

## 3. Inter-System API Contracts

### A. Admissions Ingestion Contract
- **Endpoint:** `POST /api/v1/enrollment/sync/` on `CodeCampCore`
- **Caller:** `Codecamp` (`SyncDispatcher.sync_to_core_erp`)
- **Headers:** `X-API-KEY: <CORE_API_KEY>` or `Authorization: Bearer <CORE_API_KEY>`
- **Payload:**
```json
{
  "registration_code": "TC-2026-0042",
  "first_name": "Alexander",
  "last_name": "Smith",
  "email": "guardian@example.com",
  "phone": "+2348012345678",
  "course_name": "Teen CodeCamp",
  "batch_name": "Morning Batch A",
  "external_attendance_id": "STU-10042",
  "parent": {
    "name": "Jane Smith",
    "phone": "+2348012345678",
    "whatsapp": "+2348012345678",
    "email": "guardian@example.com",
    "relationship": "Mother"
  },
  "payment": {
    "amount_paid": 30000.0,
    "status": "paid",
    "reference": "REF-789012"
  }
}
```

### B. Daily Attendance Push Contract
- **Endpoint:** `POST /api/v1/attendance/sync/` on `CodeCampCore`
- **Caller:** `attendance-system` (`CoreAttendanceSyncService`)
- **Headers:** `X-API-KEY: <CORE_API_KEY>`
- **Payload:**
```json
{
  "records": [
    {
      "external_student_id": "STU-10042",
      "student_username": "stu-10042",
      "date": "2026-08-07",
      "status": "Present",
      "check_in": "08:45:00",
      "check_out": "14:15:00",
      "source": "kiosk_qr_scanner",
      "external_reference": "ATT-5421"
    }
  ]
}
```

---

## 4. Multi-Tenant SaaS Evolution Roadmap

To transition this 3-tier architecture into a multi-tenant commercial SaaS:

### Phase A: Tenant Isolation & Identification
1. Introduce `Organization` / `Tenant` model in `CodeCampCore`:
   - Unique `tenant_slug` (e.g. `techacademy`, `codingjuniors`).
   - Domain routing (e.g. `techacademy.codecamp.app` or custom domain `portal.techacademy.org`).
2. Attach `tenant_id` foreign keys to all Academic & Financial models.

### Phase B: API Key Scoping by Tenant
- Update `CoreAPIKeyAuthentication` to resolve not just global M2M keys, but tenant-scoped keys `(tenant, api_key_hash)`.
- Pass `X-TENANT-ID` header in cross-system HTTP requests.

### Phase C: White-Label Admissions & Attendance
- Allow `Codecamp` to dynamically render branding (logos, color schemes, pricing tiers) based on the target tenant subdomain.
- In `attendance-system`, partition students and attendance logs by `tenant_id` with role-based kiosk permissions per campus/branch.

### Phase D: Automated Billing & Subscriptions
- Integrate Stripe / Paystack Subscriptions in `CodeCampCore` SuperAdmin dashboard to meter usage (active students per month, SMS/WhatsApp alert credits).
