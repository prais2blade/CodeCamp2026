from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required as staff_required
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic.edit import CreateView

from teencamp.forms import CodingCampRegistrationForm
from teencamp.models import (
    CodingCampRegistration,
    STANDARD_PRICE,
    DISCOUNT_RATE,
    EARLY_BIRD_LIMIT,
    MAX_CAPACITY,
)

from teencamp.services.registration_submission_service import (
    RegistrationSubmissionService,
)

BANK_INFO = (
    "Praisetent Info & Tech · "
    "Keystone Bank · 1000087660"
)


class CampLanding(View):

    template_name = "teencamp/landing.html"

    def get(self, request):

        total = CodingCampRegistration.objects.count()

        seats_left_early = max(
            0,
            EARLY_BIRD_LIMIT - total,
        )

        seats_left_total = max(
            0,
            MAX_CAPACITY - total,
        )

        current_price = (
            STANDARD_PRICE * (1 - DISCOUNT_RATE)
            if seats_left_early
            else STANDARD_PRICE
        )

        return render(
            request,
            self.template_name,
            {
                "bank_info": BANK_INFO,
                "price_now": f"{current_price:,.0f}",
                "seats_left_early": seats_left_early,
                "seats_left_total": seats_left_total,
            },
        )


class CampRegister(View):

    template_name = "teencamp/register.html"

    success_url = reverse_lazy(
        "teencamp:success"
    )

    def get(self, request):

        return render(
            request,
            self.template_name,
            {
                "form": CodingCampRegistrationForm(),
                "bank_info": BANK_INFO,
            },
        )

    def post(self, request):

        form = CodingCampRegistrationForm(
            request.POST,
            request.FILES,
        )

        if not form.is_valid():

            return render(
                request,
                self.template_name,
                {
                    "form": form,
                    "bank_info": BANK_INFO,
                },
            )

        try:

            registration = (
                RegistrationSubmissionService.submit(
                    form
                )
            )

        except ValueError as exc:

            form.add_error(
                None,
                str(exc),
            )

            return render(
                request,
                self.template_name,
                {
                    "form": form,
                    "bank_info": BANK_INFO,
                },
            )

        messages.success(
            request,
            (
                f"Registration received successfully. "
                f"Your registration code is "
                f"{registration.reg_code}. "
                "Your payment will now be reviewed."
            ),
        )

        return redirect(
            "teencamp:success",
            reg_code=registration.reg_code,
        )
        
# ==========================================================
# Virtual Registration
# ==========================================================

class VirtualRegistrationView(CreateView):

    model = CodingCampRegistration

    form_class = CodingCampRegistrationForm

    template_name = (
        "teencamp/virtual_register.html"
    )

    success_url = reverse_lazy(
        "teencamp:success"
    )

    def get_initial(self):

        initial = super().get_initial()

        initial["mode"] = "VIRTUAL"

        return initial

    def form_valid(self, form):

        form.instance.mode = "VIRTUAL"

        try:

            registration = (
                RegistrationSubmissionService.submit(
                    form
                )
            )

        except ValueError as exc:

            form.add_error(
                None,
                str(exc),
            )

            return self.form_invalid(
                form
            )

        messages.success(
            self.request,
            (
                f"Registration received successfully. "
                f"Your registration code is "
                f"{registration.reg_code}. "
                "Your payment will now be reviewed."
            ),
        )

        return redirect(
            "teencamp:success",
            reg_code=registration.reg_code,
        )


# ==========================================================
# Success Page
# ==========================================================

from django.shortcuts import get_object_or_404, render
from django.views import View

from teencamp.models import CodingCampRegistration


class CampSuccess(View):

    template_name = "teencamp/success.html"

    def get(self, request, reg_code):

        registration = get_object_or_404(
            CodingCampRegistration,
            reg_code=reg_code,
        )

        context = {
            "registration": registration,
        }

        return render(
            request,
            self.template_name,
            context,
        )
        
        
from django.contrib import messages
from django.shortcuts import redirect

from teencamp.services.pending_sync_service import (
    PendingAttendanceSyncService,
)

@staff_required
def sync_pending_registrations(request):

    result = PendingAttendanceSyncService.sync_all()

    messages.success(
        request,
        (
            f"Synchronization complete. "
            f"{result['success']} synced, "
            f"{result['failed']} failed."
        )
    )

    return redirect("backoffice:dashboard")