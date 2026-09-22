from typing import Tuple, Dict, Any
from django.db.models import Q
from apps.accounts.models import Profile
from apps.courses.models import Course
from apps.scheduling.models import Batch


class QuotaExceededException(Exception):
    """Raised when an action violates the tenant's active tier quota."""
    def __init__(self, message: str, quota_type: str, current: int, limit: int):
        self.message = message
        self.quota_type = quota_type
        self.current = current
        self.limit = limit
        super().__init__(self.message)


TIER_LIMITS = {
    'starter': {
        'name': 'Starter Tier',
        'max_students': 50,
        'max_courses': 3,
        'max_batches': 5,
        'max_api_keys': 2,
        'max_domains': 1,
        'custom_branding': False,
        'webhook_access': False,
    },
    'pro': {
        'name': 'Professional Tier',
        'max_students': 500,
        'max_courses': 20,
        'max_batches': 30,
        'max_api_keys': 10,
        'max_domains': 5,
        'custom_branding': True,
        'webhook_access': True,
    },
    'enterprise': {
        'name': 'Enterprise Tier',
        'max_students': 5000,
        'max_courses': 9999,
        'max_batches': 9999,
        'max_api_keys': 100,
        'max_domains': 50,
        'custom_branding': True,
        'webhook_access': True,
    },
}


class TenantQuotaService:
    @staticmethod
    def get_tier_limits(tenant) -> Dict[str, Any]:
        tier = (tenant.subscription_tier or 'starter').lower()
        limits = TIER_LIMITS.get(tier, TIER_LIMITS['starter']).copy()
        # Override student limit if customized on the tenant model
        if tenant.max_students and tenant.max_students > 0:
            limits['max_students'] = tenant.max_students
        return limits

    @classmethod
    def get_usage_metrics(cls, tenant) -> Dict[str, Any]:
        limits = cls.get_tier_limits(tenant)

        # 1. Students Count
        student_filter = Q(tenant=tenant)
        if tenant.is_default:
            student_filter |= Q(tenant__isnull=True)
        student_count = Profile.objects.filter(student_filter, role='student').count()

        # 2. Courses Count
        course_count = Course.objects.filter(tenant=tenant).count()

        # 3. Batches Count
        batch_count = Batch.objects.filter(tenant=tenant).count()

        # 4. API Keys Count
        api_key_count = tenant.api_keys.filter(is_active=True).count()

        # 5. Domains Count
        domain_count = tenant.domains.count()

        def compute_percentage(current: int, limit: int) -> int:
            if limit <= 0 or limit >= 9999:
                return min(100, int((current / 1000) * 100)) if limit >= 9999 else 100
            return min(100, int((current / limit) * 100))

        return {
            'tier': tenant.subscription_tier or 'starter',
            'tier_name': limits['name'],
            'students': {
                'current': student_count,
                'limit': limits['max_students'],
                'percentage': compute_percentage(student_count, limits['max_students']),
                'is_near_limit': student_count >= int(limits['max_students'] * 0.85),
                'is_exceeded': student_count >= limits['max_students'],
            },
            'courses': {
                'current': course_count,
                'limit': limits['max_courses'],
                'percentage': compute_percentage(course_count, limits['max_courses']),
                'is_near_limit': course_count >= int(limits['max_courses'] * 0.85),
                'is_exceeded': course_count >= limits['max_courses'],
            },
            'batches': {
                'current': batch_count,
                'limit': limits['max_batches'],
                'percentage': compute_percentage(batch_count, limits['max_batches']),
                'is_near_limit': batch_count >= int(limits['max_batches'] * 0.85),
                'is_exceeded': batch_count >= limits['max_batches'],
            },
            'api_keys': {
                'current': api_key_count,
                'limit': limits['max_api_keys'],
                'percentage': compute_percentage(api_key_count, limits['max_api_keys']),
                'is_near_limit': api_key_count >= int(limits['max_api_keys'] * 0.85),
                'is_exceeded': api_key_count >= limits['max_api_keys'],
            },
            'domains': {
                'current': domain_count,
                'limit': limits['max_domains'],
                'percentage': compute_percentage(domain_count, limits['max_domains']),
                'is_near_limit': domain_count >= int(limits['max_domains'] * 0.85),
                'is_exceeded': domain_count >= limits['max_domains'],
            },
            'features': {
                'custom_branding': limits['custom_branding'],
                'webhook_access': limits['webhook_access'],
            }
        }

    @classmethod
    def can_enroll_student(cls, tenant) -> Tuple[bool, str]:
        usage = cls.get_usage_metrics(tenant)['students']
        if usage['is_exceeded']:
            return False, f"Enrollment quota reached ({usage['current']}/{usage['limit']} students). Upgrade subscription tier to register more students."
        return True, "Within quota"

    @classmethod
    def can_create_course(cls, tenant) -> Tuple[bool, str]:
        usage = cls.get_usage_metrics(tenant)['courses']
        if usage['is_exceeded']:
            return False, f"Course creation limit reached ({usage['current']}/{usage['limit']} courses). Upgrade your plan to add more curriculum."
        return True, "Within quota"

    @classmethod
    def can_create_batch(cls, tenant) -> Tuple[bool, str]:
        usage = cls.get_usage_metrics(tenant)['batches']
        if usage['is_exceeded']:
            return False, f"Batch cohort limit reached ({usage['current']}/{usage['limit']} batches). Upgrade your plan to create more cohorts."
        return True, "Within quota"

    @classmethod
    def can_create_api_key(cls, tenant) -> Tuple[bool, str]:
        usage = cls.get_usage_metrics(tenant)['api_keys']
        if usage['is_exceeded']:
            return False, f"API Key limit reached ({usage['current']}/{usage['limit']} keys). Upgrade plan to provision more M2M scanner keys."
        return True, "Within quota"

    @classmethod
    def can_create_domain(cls, tenant) -> Tuple[bool, str]:
        usage = cls.get_usage_metrics(tenant)['domains']
        if usage['is_exceeded']:
            return False, f"Custom domain quota reached ({usage['current']}/{usage['limit']} domains). Upgrade your plan to map additional custom URLs."
        return True, "Within quota"
