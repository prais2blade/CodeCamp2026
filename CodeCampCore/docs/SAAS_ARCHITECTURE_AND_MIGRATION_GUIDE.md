# Multi-Tenant SaaS Architecture & Post-Summer Migration Guide

## 1. System Ecosystem & Strategic Vision

The ecosystem consists of three standalone yet seamlessly integrated platforms:

```
+------------------------------------+        +----------------------------------------+
|    CodeCamp Summer Registration    |        |        Attendance Kiosk System         |
|   (Public Registrations & Intake)  |        |    (Physical QR Scanner & Check-in)    |
|   - 6-Week Summer Cohort Reg       |        |   - Summer Students (via Integration)  |
|   - Payment & Camp Batching        |        |   - Direct Regular Students (4/6/18 mo)|
+-----------------+------------------+        +-------------------+--------------------+
                  |                                               |
                  | API Sync / M2M Key                            | API Sync / M2M Key
                  v                                               v
+--------------------------------------------------------------------------------------+
|                           CodeCampCore Multi-Tenant SaaS                             |
|                           (Central Academy Management)                               |
|                                                                                      |
|   +--------------------------+  +--------------------------+  +------------------+   |
|   |  Tenant: Lagos Campus    |  |  Tenant: Abuja Campus    |  |  Tenant: Online  |   |
|   |  - 6-Week Summer Camp    |  |  - 6-Week Summer Camp    |  |  - Full Academy  |   |
|   |  - 4/6/18-Month Programs |  |  - 4/6/18-Month Programs |  |  - Subscriptions |   |
|   +--------------------------+  +--------------------------+  +------------------+   |
+--------------------------------------------------------------------------------------+
```

---

## 2. Multi-Tenant Architecture & Isolation Model

### Tenant Isolation Pattern
- Every organization (Academy Campus, Partner School, Franchise) is an isolated `Tenant`.
- Models inherit from `TenantAwareModel` and are filtered automatically by `TenantMiddleware` using:
  1. Subdomain resolution (`lagos.codecamp.org` -> Tenant `lagos-hq`).
  2. Custom verified domain (`academy.brand.com` -> Tenant `brand`).
  3. M2M API Key header (`X-API-KEY: cc_live_...` -> Tenant).
  4. Explicit superuser context switcher (`?switch_tenant=slug`).

### SaaS Subscription Quota Tiers
| Metric / Feature | Starter Tier | Professional Tier | Enterprise Tier |
| :--- | :--- | :--- | :--- |
| **Max Active Students** | 50 | 500 | 5,000+ |
| **Courses Allowed** | 3 | 20 | Unlimited |
| **Batches / Cohorts** | 5 | 30 | Unlimited |
| **M2M API Keys** | 2 | 10 | 100 |
| **Custom Domains** | 1 | 5 | 50 |
| **Parent Email Alerts** | Included | Included | Priority Delivery |
| **Outbound Webhooks** | No | Included | Included (Signed HMAC) |

---

## 3. Handling Summer vs. Direct Academy Students

During the live 6-week summer program:
1. **Summer Camp Registrations**:
   - Enrolled through `codecamp` (Summer Registration app).
   - Synchronized with `attendance-system` using integration keys.
   - Mapped to **Summer Coding & Robotics Camp (6 Weeks)** with specific time/mode cohorts.
2. **Direct Academy Enrollments (Non-Summer 4, 6, 18-month tracks)**:
   - Enrolled directly into `attendance-system` so they can immediately utilize QR check-in hardware.
   - Identified by `integration_key = NULL` and assigned `class_name` (e.g. *"Programing Advance"*, *"Morning Batch A"*).
   - Intelligently mapped by the data importer into dedicated **Full Academy Programs** (16–24+ weeks duration) and distinct cohorts.

---

## 4. Post-Summer Migration Strategy (After 6 Weeks)

When the 6-week summer program finishes and students graduate or transition to 4-month, 6-month, or 18-month full courses:

### Step 1: Run Full Data Importer in Dry-Run Mode
```bash
python manage.py import_live_summer_cohort --tenant-slug lagos-hq --dry-run
```
*Verify that batch counts, student accounts, and total attendance records match expectation.*

### Step 2: Execute Live Migration
```bash
python manage.py import_live_summer_cohort --tenant-slug lagos-hq
```

### Step 3: Transition Summer Graduates to Full Academy Programs
1. Log into the Tenant Console (`/tenants/dashboard/`).
2. Summer students who enrolled for continuing 4/6/18-month diploma tracks can be transitioned to the new program batch with one click, preserving their full summer attendance history and student QR code ID.
