from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

from apps.tenants.models import Tenant, TenantDomain, TenantAPIKey
from apps.tenants.services import TenantQuotaService
from apps.accounts.models import Profile

User = get_user_model()


class SaaSQuotasAndTiersTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Admin user
        self.admin_user = User.objects.create_superuser(
            username="saas_admin",
            email="saas_admin@test.com",
            password="admin-safe-password-123",
        )
        self.client.force_login(self.admin_user)

        # Starter Tier Tenant (Limit: 50 students, 2 API Keys, 1 Domain)
        self.starter_tenant = Tenant.objects.create(
            name="Beta Coding Hub",
            slug="beta-hub",
            subdomain="beta",
            subscription_tier="starter",
            max_students=50,
            is_default=False,
        )

    def test_quota_service_tier_limits(self):
        starter_limits = TenantQuotaService.get_tier_limits(self.starter_tenant)
        self.assertEqual(starter_limits['max_students'], 50)
        self.assertEqual(starter_limits['max_api_keys'], 2)
        self.assertEqual(starter_limits['max_domains'], 1)

    def test_quota_service_blocks_when_limit_reached(self):
        # Create 2 API Keys (reaching starter limit)
        TenantAPIKey.objects.create(tenant=self.starter_tenant, name="Key 1", is_active=True)
        TenantAPIKey.objects.create(tenant=self.starter_tenant, name="Key 2", is_active=True)

        can_create_key, reason = TenantQuotaService.can_create_api_key(self.starter_tenant)
        self.assertFalse(can_create_key)
        self.assertIn("API Key limit reached", reason)

        # Create 1 Domain (reaching starter limit)
        TenantDomain.objects.create(tenant=self.starter_tenant, domain="beta.hub.com")

        can_create_domain, reason = TenantQuotaService.can_create_domain(self.starter_tenant)
        self.assertFalse(can_create_domain)
        self.assertIn("Custom domain quota reached", reason)

    def test_api_key_create_view_enforces_quota(self):
        # 1st Key succeeds
        response1 = self.client.post(
            f"{reverse('tenants:api_key_create')}?switch_tenant=beta-hub",
            {"name": "Scanner 1"},
            follow=True,
        )
        self.assertEqual(self.starter_tenant.api_keys.count(), 1)

        # 2nd Key succeeds
        response2 = self.client.post(
            f"{reverse('tenants:api_key_create')}?switch_tenant=beta-hub",
            {"name": "Scanner 2"},
            follow=True,
        )
        self.assertEqual(self.starter_tenant.api_keys.count(), 2)

        # 3rd Key is BLOCKED by Quota
        response3 = self.client.post(
            f"{reverse('tenants:api_key_create')}?switch_tenant=beta-hub",
            {"name": "Scanner 3"},
            follow=True,
        )
        self.assertEqual(self.starter_tenant.api_keys.count(), 2)
        self.assertContains(response3, "API Key limit reached")

    def test_domain_add_view_enforces_quota(self):
        # 1st Domain succeeds
        response1 = self.client.post(
            f"{reverse('tenants:domain_add')}?switch_tenant=beta-hub",
            {"domain": "code.betahub.org", "is_primary": "on"},
            follow=True,
        )
        self.assertEqual(self.starter_tenant.domains.count(), 1)

        # 2nd Domain is BLOCKED by Quota
        response2 = self.client.post(
            f"{reverse('tenants:domain_add')}?switch_tenant=beta-hub",
            {"domain": "portal.betahub.org"},
            follow=True,
        )
        self.assertEqual(self.starter_tenant.domains.count(), 1)
        self.assertContains(response2, "Custom domain quota reached")

    def test_tenant_plan_upgrade_flow(self):
        # Upgrade to Pro
        response = self.client.post(
            f"{reverse('tenants:plan_upgrade')}?switch_tenant=beta-hub",
            {"target_tier": "pro"},
            follow=True,
        )
        self.starter_tenant.refresh_from_db()
        self.assertEqual(self.starter_tenant.subscription_tier, "pro")
        self.assertEqual(self.starter_tenant.max_students, 500)
        self.assertContains(response, "Successfully upgraded")

        # Now can create more API keys under Pro tier (limit 10)
        TenantAPIKey.objects.create(tenant=self.starter_tenant, name="Key 1", is_active=True)
        TenantAPIKey.objects.create(tenant=self.starter_tenant, name="Key 2", is_active=True)
        can_create_more, _ = TenantQuotaService.can_create_api_key(self.starter_tenant)
        self.assertTrue(can_create_more)
