# Automated Test Suite Documentation

The automated testing architecture for **CodeCampCore** consists of 35 comprehensive unit and integration tests across 7 distinct test modules.

---

## 1. Test Suite Breakdown

| Module File | Area Covered | Number of Tests | Key Test Cases |
| :--- | :--- | :--- | :--- |
| `tests/test_tenant_console.py` | Tenant Console UI & Actions | 7 | Dashboard KPIs, API Key list & generation, API key revocation, custom domain mapping, live attendance streaming, settings update. |
| `tests/test_data_importer.py` | Live Summer & Direct Cohort Importer | 2 | Dry-run rollback verification, live transaction commit, batch & student mapping, attendance check-in synchronization. |
| `tests/test_saas_quotas.py` | Subscription Quota Enforcement | 5 | Starter/Pro/Enterprise tier capacity, student enrollment limits, course limits, API key limits, in-app tier upgrade flow. |
| `tests/test_tenant_notifications.py` | Parent Alerts & Outbound Webhooks | 3 | Present check-in emails, Absent notice emails, HMAC SHA-256 digital signature generation and HTTP webhook dispatch. |
| `tests/test_auth_flows.py` | User Authentication & Onboarding | 5 | Username/password login, password reset tokens, student redirection, staff permissions, onboarding completion. |
| `tests/test_attendance_service.py` | Kiosk Attendance Ingestion | 3 | M2M API Key validation, bulk attendance recording, multi-tenant data isolation. |
| `tests/test_integration_flow.py` | End-to-End Simulation Pipeline | 10 | Complete lifecycle simulation from summer camp intake to QR kiosk scanning, tenant isolation, and quota protection. |

---

## 2. How to Run the Tests

### Run Full Test Suite (35 Tests)
```bash
python manage.py test
```

### Run Specific Test Modules
```bash
# Test Tenant Admin Console
python manage.py test tests.test_tenant_console

# Test Live Data Importer
python manage.py test tests.test_data_importer

# Test SaaS Tier Quotas
python manage.py test tests.test_saas_quotas

# Test Parent Alerts and Webhooks
python manage.py test tests.test_tenant_notifications
```

---

## 3. Continuous Integration (CI/CD GitHub Actions Example)

```yaml
name: CodeCampCore SaaS CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install Dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      - name: Run Migrations
        run: python manage.py migrate
      - name: Run Test Suite
        run: python manage.py test
```
