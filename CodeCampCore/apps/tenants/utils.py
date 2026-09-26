import os
import base64
from django.conf import settings
from .models import Tenant
from .context import get_current_tenant


def get_tenant_signatory_data(tenant=None, request=None):
    """
    Returns the active tenant, director name, director title,
    and a base64 Data URI of the director signature for crisp rendering
    in browser HTML as well as WeasyPrint / PDF generation.
    """
    if not tenant and request:
        tenant = get_current_tenant()
        if not tenant and hasattr(request, 'user') and request.user.is_authenticated and hasattr(request.user, 'profile'):
            tenant = request.user.profile.tenant

    if not tenant:
        tenant = Tenant.objects.filter(is_default=True).first() or Tenant.objects.first()

    director_name = tenant.director_name if tenant and tenant.director_name else "Director of Academic Affairs"
    director_title = tenant.director_title if tenant and tenant.director_title else "Academic Director & Lead Instructor"
    signature_data_uri = None
    signature_url = None

    if tenant and tenant.director_signature:
        try:
            signature_url = tenant.director_signature.url
        except Exception:
            signature_url = None

        try:
            sig_path = tenant.director_signature.path
            if os.path.exists(sig_path):
                with open(sig_path, 'rb') as f:
                    b64 = base64.b64encode(f.read()).decode('utf-8')
                    ext = sig_path.split('.')[-1].lower()
                    mime = 'image/png' if ext == 'png' else 'image/jpeg'
                    signature_data_uri = f"data:{mime};base64,{b64}"
        except Exception:
            pass

    return {
        'tenant': tenant,
        'director_name': director_name,
        'director_title': director_title,
        'director_signature_url': signature_url,
        'director_signature_data_uri': signature_data_uri,
    }
