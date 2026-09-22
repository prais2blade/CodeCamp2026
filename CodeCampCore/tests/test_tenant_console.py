from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.tenants.models import Tenant, TenantDomain, TenantAPIKey
from apps.accounts.models import Profile, Attendance
from apps.courses.models import Course, Subject
from apps.scheduling.models import Batch

User = get_user_model()


class TenantConsoleTests(TestCase):
    def setUp(self):
        self.client = Client()

        # 1. Create Tenants
        self.tenant_lagos = Tenant.objects.create(
            name="CodeCamp Lagos HQ",
            slug="lagos-hq",
            subdomain="lagos",
            subscription_tier="enterprise",
            max_students=1000,
            is_default=True,
            is_active=True,
        )

        self.tenant_abuja = Tenant.objects.create(
            name="CodeCamp Abuja Hub",
            slug="abuja-hub",
            subdomain="abuja",
            subscription_tier="starter",
            max_students=50,
            is_default=False,
            is_active=True,
        )

        # 2. Create Superuser Admin
        self.admin_user = User.objects.create_superuser(
            username="superadmin",
            email="admin@codecamp.org",
            password="adminpassword123",
        )
        admin_prof = self.admin_user.profile
        admin_prof.role = "hod"
        admin_prof.tenant = self.tenant_lagos
        admin_prof.is_verified = True
        admin_prof.is_approved = True
        admin_prof.onboarding_stage = "finished"
        admin_prof.save()

        # 3. Create Lagos Student
        self.student_lagos = User.objects.create_user(
            username="lagos_student",
            email="student@lagos.org",
            password="studentpass123",
        )
        student_prof = self.student_lagos.profile
        student_prof.role = "student"
        student_prof.tenant = self.tenant_lagos
        student_prof.is_verified = True
        student_prof.is_approved = True
        student_prof.onboarding_stage = "finished"
        student_prof.external_attendance_id = "LAG-101"
        student_prof.save()

        # 4. Create Course & Attendance
        self.course = Course.objects.create(
            tenant=self.tenant_lagos,
            name="Cloud Architecture",
            is_published=True,
        )
        self.subject = Subject.objects.create(
            name="Kubernetes & DevOps",
            course=self.course,
        )
        self.batch = Batch.objects.create(
            tenant=self.tenant_lagos,
            name="Cohort A",
            course=self.course,
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timezone.timedelta(days=60),
            is_published=True,
        )
        self.attendance = Attendance.objects.create(
            tenant=self.tenant_lagos,
            student=self.student_lagos,
            subject=self.subject,
            batch=self.batch,
            date=timezone.localdate(),
            status="Present",
            check_in_time=timezone.now().time(),
            source="kiosk_lagos_gate1",
        )

    def test_anonymous_user_redirected_to_login(self):
        response = self.client.get(reverse("tenants:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/account/login/", response.url)

    def test_student_user_forbidden_from_tenant_console(self):
        self.client.force_login(self.student_lagos)
        response = self.client.get(reverse("tenants:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/account/login/", response.url)

    def test_admin_dashboard_renders_metrics_successfully(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("tenants:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "tenants/dashboard.html")
        self.assertEqual(response.context["total_students"], 1)
        self.assertEqual(response.context["today_scans"], 1)
        self.assertEqual(response.context["present_today"], 1)
        self.assertEqual(response.context["tenant"].slug, "lagos-hq")

    def test_api_key_generation_and_revocation(self):
        self.client.force_login(self.admin_user)

        # Generate API key
        post_data = {"name": "Lagos Main Entrance Kiosk"}
        response = self.client.post(reverse("tenants:api_key_create"), post_data, follow=True)
        self.assertEqual(response.status_code, 200)

        api_key_obj = TenantAPIKey.objects.filter(tenant=self.tenant_lagos, name="Lagos Main Entrance Kiosk").first()
        self.assertIsNotNone(api_key_obj)
        self.assertTrue(api_key_obj.is_active)
        self.assertTrue(api_key_obj.key.startswith("cc_live_"))

        # Revoke API key
        revoke_url = reverse("tenants:api_key_revoke", kwargs={"key_id": api_key_obj.id})
        response = self.client.post(revoke_url, follow=True)
        self.assertEqual(response.status_code, 200)

        api_key_obj.refresh_from_db()
        self.assertFalse(api_key_obj.is_active)

    def test_domain_management(self):
        self.client.force_login(self.admin_user)

        # Add domain
        add_data = {
            "domain": "lagos.codecamp.org",
            "is_primary": "on",
        }
        response = self.client.post(reverse("tenants:domain_add"), add_data, follow=True)
        self.assertEqual(response.status_code, 200)

        domain_obj = TenantDomain.objects.filter(tenant=self.tenant_lagos, domain="lagos.codecamp.org").first()
        self.assertIsNotNone(domain_obj)
        self.assertTrue(domain_obj.is_primary)

        # Delete domain
        delete_url = reverse("tenants:domain_delete", kwargs={"domain_id": domain_obj.id})
        response = self.client.post(delete_url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(TenantDomain.objects.filter(id=domain_obj.id).exists())

    def test_live_attendance_feed_and_filtering(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("tenants:attendance_live"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "tenants/attendance_live.html")
        self.assertEqual(response.context["total_records"], 1)

        # Filter by student query
        response = self.client.get(reverse("tenants:attendance_live") + "?q=lagos_student")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_records"], 1)

        # Filter by non-existent query
        response = self.client.get(reverse("tenants:attendance_live") + "?q=non_existent_name")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_records"], 0)

    def test_tenant_settings_update(self):
        self.client.force_login(self.admin_user)
        settings_data = {
            "name": "CodeCamp Lagos Global Tech Campus",
            "contact_email": "lagos-admin@codecamp.org",
            "contact_phone": "+234 801 234 5678",
            "address": "100 Innovation Boulevard, Lagos",
            "timezone": "Africa/Lagos",
        }
        response = self.client.post(reverse("tenants:settings"), settings_data, follow=True)
        self.assertEqual(response.status_code, 200)

        self.tenant_lagos.refresh_from_db()
        self.assertEqual(self.tenant_lagos.name, "CodeCamp Lagos Global Tech Campus")
        self.assertEqual(self.tenant_lagos.contact_email, "lagos-admin@codecamp.org")
