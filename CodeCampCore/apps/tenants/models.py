import secrets
from django.db import models
from django.utils.text import slugify
from .context import get_current_tenant


class Tenant(models.Model):
    SUBSCRIPTION_CHOICES = [
        ('starter', 'Starter Tier'),
        ('pro', 'Professional Tier'),
        ('enterprise', 'Enterprise Tier'),
    ]

    name = models.CharField(max_length=150, help_text="Academy or Organization name")
    slug = models.SlugField(max_length=100, unique=True, db_index=True, help_text="Subdomain or URL identifier")
    subdomain = models.CharField(max_length=100, unique=True, db_index=True, blank=True)
    is_active = models.BooleanField(default=True, help_text="Designates whether this tenant is operational")
    is_default = models.BooleanField(default=False, help_text="Default fallback tenant for unmatched requests")
    subscription_tier = models.CharField(max_length=20, choices=SUBSCRIPTION_CHOICES, default='pro')
    max_students = models.PositiveIntegerField(default=500, help_text="Maximum allowed student accounts")
    
    contact_name = models.CharField(max_length=120, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=50, blank=True)
    address = models.TextField(blank=True, help_text="Physical campus address")
    timezone = models.CharField(max_length=50, default='Africa/Lagos', blank=True)
    
    logo = models.ImageField(upload_to='tenants/logos/', blank=True, null=True)
    theme_color = models.CharField(max_length=20, default='#1E3A8A', help_text="Primary brand color (hex)")
    portal_title = models.CharField(max_length=150, blank=True, help_text="Custom brand header title")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Tenant'
        verbose_name_plural = 'Tenants'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.slug})"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        if not self.subdomain:
            self.subdomain = self.slug
        if not self.portal_title:
            self.portal_title = self.name
        if self.is_default:
            # Ensure only one default tenant exists
            Tenant.objects.filter(is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class TenantDomain(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='domains')
    domain = models.CharField(max_length=255, unique=True, db_index=True, help_text="Custom domain or host (e.g. lagos.codecamp.org)")
    is_primary = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=True, help_text="DNS resolution status")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Tenant Domain'
        verbose_name_plural = 'Tenant Domains'

    def __str__(self):
        return f"{self.domain} -> {self.tenant.name}"

    def save(self, *args, **kwargs):
        if self.is_primary:
            TenantDomain.objects.filter(tenant=self.tenant, is_primary=True).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)


class TenantAPIKey(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='api_keys')
    name = models.CharField(max_length=100, default='Default M2M Ingestion Key', help_text="Descriptive client label (e.g. Summer Camp Gateway, Kiosk Scanner)")
    key = models.CharField(max_length=128, unique=True, db_index=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Tenant API Key'
        verbose_name_plural = 'Tenant API Keys'

    def __str__(self):
        return f"{self.tenant.slug} - {self.name}"

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = f"cc_live_{secrets.token_urlsafe(32)}"
        super().save(*args, **kwargs)


class TenantWebhookEndpoint(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='webhooks')
    target_url = models.URLField(max_length=500, help_text="Destination HTTPS URL for real-time payloads")
    secret = models.CharField(max_length=128, blank=True, help_text="HMAC secret for request payload verification")
    events = models.CharField(
        max_length=255,
        default="attendance.all,student.enrolled",
        help_text="Comma-separated event topics (e.g. attendance.checkin, attendance.absent, student.enrolled)"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_dispatched_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Tenant Webhook Endpoint'
        verbose_name_plural = 'Tenant Webhook Endpoints'

    def __str__(self):
        return f"{self.tenant.slug} -> {self.target_url}"

    def save(self, *args, **kwargs):
        if not self.secret:
            self.secret = f"whsec_{secrets.token_hex(24)}"
        super().save(*args, **kwargs)


class TenantQuerySet(models.QuerySet):
    def for_tenant(self, tenant):
        if tenant is None:
            return self
        return self.filter(tenant=tenant)

    def current_tenant(self):
        tenant = get_current_tenant()
        if tenant:
            return self.filter(tenant=tenant)
        return self


class TenantManager(models.Manager.from_queryset(TenantQuerySet)):
    def get_queryset(self):
        qs = super().get_queryset()
        current_tenant = get_current_tenant()
        if current_tenant:
            return qs.filter(tenant=current_tenant)
        return qs


class TenantAwareModel(models.Model):
    """
    Abstract base class for models that belong to an isolated academy tenant.
    """
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="%(app_label)s_%(class)s_records",
        null=True,
        blank=True,
        db_index=True,
        help_text="Tenant that owns this record",
    )

    objects = models.Manager()  # standard unfiltered manager for background/admin
    tenant_objects = TenantManager()  # tenant-isolated manager

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self.tenant_id:
            current_tenant = get_current_tenant()
            if current_tenant:
                self.tenant = current_tenant
        super().save(*args, **kwargs)
