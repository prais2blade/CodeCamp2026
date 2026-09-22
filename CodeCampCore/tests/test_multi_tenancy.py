import json
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.tenants.models import Tenant, TenantDomain, TenantAPIKey
from apps.accounts.models import Profile, Attendance
from apps.courses.models import Course, Subject
from apps.scheduling.models import Batch

User = get_user_model()


class MultiTenancyIsolationTests(TestCase):
    """
    Tests proving multi-tenant architecture, tenant resolution middleware,
    tenant-specific API key authentication, and database isolation.
    """

    def setUp(self):
        # Create 2 distinct tenants
        self.tenant_lagos = Tenant.objects.create(
            name="CodeCamp Lagos Main Academy",
            slug="lagos",
            subdomain="lagos",
            is_default=True,
            is_active=True,
            subscription_tier="enterprise",
        )
        self.tenant_abuja = Tenant.objects.create(
            name="CodeCamp Abuja Tech Campus",
            slug="abuja",
            subdomain="abuja",
            is_default=False,
            is_active=True,
            subscription_tier="pro",
        )

        # Create Tenant Domains
        TenantDomain.objects.create(
            tenant=self.tenant_lagos,
            domain="lagos.codecamp.org",
            is_primary=True,
        )
        TenantDomain.objects.create(
            tenant=self.tenant_abuja,
            domain="abuja.codecamp.org",
            is_primary=True,
        )

        # Create Tenant-specific API Keys
        self.key_lagos = TenantAPIKey.objects.create(
            tenant=self.tenant_lagos,
            name="Lagos Admissions Gateway Key",
        )
        self.key_abuja = TenantAPIKey.objects.create(
            tenant=self.tenant_abuja,
            name="Abuja Kiosk Scanner Key",
        )

        self.client = Client()

    def test_tenant_resolution_via_header(self):
        """Verify middleware sets tenant according to X-Tenant-Slug header."""
        res = self.client.get(
            "/api/v1/ping/",
            HTTP_X_TENANT_SLUG="abuja",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("X-Tenant-Slug"), "abuja")

    def test_tenant_resolution_via_domain(self):
        """Verify middleware sets tenant according to request Host domain."""
        res = self.client.get(
            "/api/v1/ping/",
            HTTP_HOST="lagos.codecamp.org",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("X-Tenant-Slug"), "lagos")

    def test_tenant_api_key_authentication_and_scoped_enrollment(self):
        """
        Verify that using a tenant's API key automatically assigns
        the created user and profile to that tenant.
        """
        payload = {
            "registration_code": "ABJ-2026-001",
            "first_name": "Fatima",
            "last_name": "Bello",
            "email": "fatima.bello@abuja-tech.com",
            "phone": "+2348099887766",
            "course_name": "Full Stack Web Development",
            "batch_name": "Abuja Cohort 1",
            "external_attendance_id": "ABJ-SCAN-101",
        }

        response = self.client.post(
            "/api/v1/enrollment/sync/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_API_KEY=self.key_abuja.key,
        )

        self.assertIn(response.status_code, [200, 201])
        data = response.json()
        
        user = User.objects.get(id=data["user_id"])
        profile = user.profile
        self.assertEqual(profile.tenant, self.tenant_abuja)
        self.assertEqual(profile.course.tenant, self.tenant_abuja)
        self.assertEqual(profile.batch.tenant, self.tenant_abuja)

    def test_data_isolation_between_tenants(self):
        """
        Verify complete data segregation between Lagos and Abuja tenants.
        """
        # 1. Enroll Lagos Student
        lagos_payload = {
            "registration_code": "LAG-2026-001",
            "first_name": "Tunde",
            "last_name": "Bakare",
            "email": "tunde.lagos@example.com",
            "phone": "+2348011223344",
            "course_name": "Mobile App Engineering",
            "batch_name": "Lagos Morning Batch",
            "external_attendance_id": "LAG-SCAN-55",
        }
        res_lagos = self.client.post(
            "/api/v1/enrollment/sync/",
            data=json.dumps(lagos_payload),
            content_type="application/json",
            HTTP_X_API_KEY=self.key_lagos.key,
        )
        self.assertIn(res_lagos.status_code, [200, 201])

        # 2. Enroll Abuja Student
        abuja_payload = {
            "registration_code": "ABJ-2026-002",
            "first_name": "Amina",
            "last_name": "Yusuf",
            "email": "amina.abuja@example.com",
            "phone": "+2348055667788",
            "course_name": "Cloud DevOps Diploma",
            "batch_name": "Abuja Weekend Batch",
            "external_attendance_id": "ABJ-SCAN-77",
        }
        res_abuja = self.client.post(
            "/api/v1/enrollment/sync/",
            data=json.dumps(abuja_payload),
            content_type="application/json",
            HTTP_X_API_KEY=self.key_abuja.key,
        )
        self.assertIn(res_abuja.status_code, [200, 201])

        # 3. Sync Attendance for both
        user_lagos = User.objects.get(email="tunde.lagos@example.com")
        user_abuja = User.objects.get(email="amina.abuja@example.com")
        subject_lagos = Subject.objects.create(course=user_lagos.profile.course, name="React Native")
        subject_abuja = Subject.objects.create(course=user_abuja.profile.course, name="Kubernetes Basics")

        att_lagos_res = self.client.post(
            "/api/v1/attendance/sync/",
            data=json.dumps({
                "records": [{
                    "student_id": user_lagos.id,
                    "subject_id": subject_lagos.id,
                    "date": "2026-08-07",
                    "status": "present",
                    "check_in": "08:30:00",
                }]
            }),
            content_type="application/json",
            HTTP_X_API_KEY=self.key_lagos.key,
        )
        self.assertEqual(att_lagos_res.status_code, 200, att_lagos_res.content)

        att_abuja_res = self.client.post(
            "/api/v1/attendance/sync/",
            data=json.dumps({
                "records": [{
                    "student_id": user_abuja.id,
                    "subject_id": subject_abuja.id,
                    "date": "2026-08-07",
                    "status": "present",
                    "check_in": "09:00:00",
                }]
            }),
            content_type="application/json",
            HTTP_X_API_KEY=self.key_abuja.key,
        )
        self.assertEqual(att_abuja_res.status_code, 200, att_abuja_res.content)

        # 4. Verify Database Segregation
        lagos_profiles = Profile.objects.filter(tenant=self.tenant_lagos)
        abuja_profiles = Profile.objects.filter(tenant=self.tenant_abuja)

        self.assertEqual(lagos_profiles.count(), 1)
        self.assertEqual(abuja_profiles.count(), 1)
        self.assertEqual(lagos_profiles.first().user.email, "tunde.lagos@example.com")
        self.assertEqual(abuja_profiles.first().user.email, "amina.abuja@example.com")

        lagos_attendance = Attendance.objects.filter(tenant=self.tenant_lagos)
        abuja_attendance = Attendance.objects.filter(tenant=self.tenant_abuja)

        self.assertEqual(lagos_attendance.count(), 1)
        self.assertEqual(abuja_attendance.count(), 1)
        self.assertEqual(lagos_attendance.first().student, user_lagos)
        self.assertEqual(abuja_attendance.first().student, user_abuja)
