from datetime import date, timedelta
import csv

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from django.contrib import messages
from django.contrib.auth.views import LoginView
from django.db.models import Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views.generic import (
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
)
from django.urls import reverse_lazy
from .forms import BatchForm
from .decorators import staff_required
from .forms import CustomLoginForm

from teencamp.models import (
    Batch,
    CodingCampRegistration,
)

from teencamp.services.registration_service import (
    RegistrationService,
)

from django.contrib import messages
from django.shortcuts import redirect

from teencamp.services.registration_sync_service import (
    RegistrationSyncService,
)

AGE_BUCKETS = (
    (10, 12),
    (13, 15),
    (16, 18),
)


# ==========================================================
# Dashboard
# ==========================================================

@method_decorator(
    staff_required,
    name="dispatch",
)
class Dashboard(TemplateView):

    template_name = "backoffice/dashboard.html"

    from django.db.models import Sum
    from teencamp.models import Batch, CodingCampRegistration


    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        registrations = CodingCampRegistration.objects

        context["total_regs"] = registrations.count()

        context["verified"] = registrations.filter(
            payment_verified=True
        ).count()

        context["unverified"] = registrations.filter(
            payment_verified=False
        ).count()

        context["revenue"] = (
            registrations.filter(
                payment_verified=True
            ).aggregate(
                Sum("price_paid")
            )["price_paid__sum"] or 0
        )

        context["virtual_count"] = registrations.filter(
            mode="VIRTUAL"
        ).count()

        context["physical_count"] = registrations.filter(
            mode="PHYSICAL"
        ).count()

        # ----------------------------------------
        # Batch Chart Data
        # ----------------------------------------

        batches = Batch.objects.filter(
            is_active=True
        ).order_by(
            "priority"
        )

        context["batch_data"] = [

            {
                "code": batch.code,
                "name": batch.name,
                "count": batch.current_size,
                "free": batch.remaining_seats,
            }

            for batch in batches

        ]

        # ----------------------------------------
        # Temporary placeholders
        # ----------------------------------------

        context["daily_labels"] = []

        context["daily_counts"] = []

        context["age_labels"] = [
            "8-10",
            "11-13",
            "14-16",
            "17-18",
        ]

        context["age_counts"] = [
            0,
            0,
            0,
            0,
        ]

        context["discount_yes"] = registrations.filter(
            discount_applied=True
        ).count()

        context["discount_no"] = registrations.filter(
            discount_applied=False
        ).count()

        return context


# ==========================================================
# Dashboard JSON
# ==========================================================

@staff_required
def dashboard_json(request):

    registrations = CodingCampRegistration.objects

    return JsonResponse({

        "total": registrations.count(),

        "verified": registrations.filter(
            payment_verified=True
        ).count(),

        "unverified": registrations.filter(
            payment_verified=False
        ).count(),

        "revenue": (
            registrations.filter(
                payment_verified=True
            ).aggregate(
                total=Sum("price_paid")
            )["total"] or 0
        ),

        "batches": [

            {

                "name": batch.name,

                "code": batch.code,

                "capacity": batch.capacity,

                "occupied": batch.current_size,

                "remaining": batch.remaining_seats,

            }

            for batch in Batch.objects.filter(
                is_active=True
            ).order_by("priority")

        ],

    })
    
# ==========================================================
# Registration List
# ==========================================================

@method_decorator(
    staff_required,
    name="dispatch",
)
class RegistrationList(ListView):

    model = CodingCampRegistration

    template_name = (
        "backoffice/registration_list.html"
    )

    context_object_name = (
        "registrations"
    )

    paginate_by = 25

    ordering = (
        "-created_at",
    )

    def get_queryset(self):

        queryset = (
            CodingCampRegistration.objects
            .select_related("batch")
            .order_by("-created_at")
        )

        status = self.request.GET.get("status")

        if status:
            queryset = queryset.filter(
                registration_status=status
            )

        payment = self.request.GET.get("payment")

        if payment == "verified":
            queryset = queryset.filter(
                payment_verified=True
            )

        elif payment == "pending":
            queryset = queryset.filter(
                payment_verified=False
            )

        mode = self.request.GET.get("mode")

        if mode:
            queryset = queryset.filter(
                mode=mode
            )

        search = self.request.GET.get("q")

        if search:

            queryset = queryset.filter(
                first_name__icontains=search
            ) | queryset.filter(
                last_name__icontains=search
            ) | queryset.filter(
                parent_name__icontains=search
            ) | queryset.filter(
                reg_code__icontains=search
            )

        return queryset


# ==========================================================
# Registration Detail
# ==========================================================

@method_decorator(
    staff_required,
    name="dispatch",
)
class RegistrationDetail(DetailView):

    model = CodingCampRegistration

    context_object_name = (
        "registration"
    )

    template_name = (
        "backoffice/registration_detail.html"
    )


@method_decorator(
    staff_required,
    name="dispatch",
)
class BatchDetail(DetailView):

    model = Batch

    template_name = "backoffice/batch_detail.html"

    context_object_name = "batch"

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        context["students"] = (
            CodingCampRegistration.objects
            .filter(
                batch=self.object,
                payment_verified=True,
            )
            .order_by(
                "first_name",
                "last_name",
            )
        )

        return context

# ==========================================================
# Payment Approval
# ==========================================================

from django.views.decorators.http import require_POST


@staff_required
def toggle_payment(request, pk):

    print("VIEW REACHED")

    registration = get_object_or_404(
        CodingCampRegistration,
        pk=pk,
    )

    print("REGISTRATION:", registration.reg_code)

    try:

        print("CALLING APPROVAL SERVICE")

        RegistrationService.approve(
            registration
        )

        print("APPROVAL SERVICE FINISHED")

        messages.success(
            request,
            "Approval completed."
        )

    except Exception as exc:

        print("ERROR:", repr(exc))

        messages.error(
            request,
            str(exc),
        )

    return redirect(
        "backoffice:reg-detail",
        pk=pk,
    )
# ==========================================================
# Export Registrations
# ==========================================================

@staff_required
def export_csv(request):

    registrations = (
        CodingCampRegistration.objects
        .select_related("batch")
        .order_by("-created_at")
    )

    response = HttpResponse(
        content_type="text/csv"
    )

    response[
        "Content-Disposition"
    ] = (
        'attachment; filename="registrations.csv"'
    )

    writer = csv.writer(response)

    writer.writerow([
        "Registration Code",
        "Student",
        "Parent",
        "Phone",
        "Email",
        "Mode",
        "Batch",
        "Status",
        "Payment",
        "Amount",
        "Date",
    ])

    for registration in registrations:

        writer.writerow([

            registration.reg_code,

            registration.full_name,

            registration.parent_name,

            registration.parent_phone,

            registration.parent_email,

            registration.mode,

            registration.batch.name
            if registration.batch
            else "Waiting List",

            registration.registration_status,

            "Verified"
            if registration.payment_verified
            else "Pending",

            registration.price_paid,

            registration.created_at.strftime(
                "%d-%m-%Y %H:%M"
            ),

        ])

    return response


# ==========================================================
# Simple Registration List
# ==========================================================

@staff_required
def registration_list(request):

    registrations = (
        CodingCampRegistration.objects
        .select_related("batch")
        .order_by("-created_at")
    )

    return render(
        request,
        "backoffice/registration_list.html",
        {
            "registrations": registrations,
        },
    )


# ==========================================================
# Staff Login
# ==========================================================

class StaffLoginView(LoginView):

    template_name = (
        "backoffice/login.html"
    )

    authentication_form = (
        CustomLoginForm
    )

    redirect_authenticated_user = True

    def get_success_url(self):

        return "/backoffice/"
    
# ==========================================================
# Dashboard WebSocket Broadcast
# ==========================================================

def broadcast_dashboard_update():
    """
    Broadcast dashboard statistics to all connected
    backoffice dashboard clients.
    """

    channel_layer = get_channel_layer()

    registrations = CodingCampRegistration.objects

    async_to_sync(
        channel_layer.group_send
    )(
        "dashboard",
        {
            "type": "dashboard.update",
            "data": {

                "total": registrations.count(),

                "verified": registrations.filter(
                    payment_verified=True
                ).count(),

                "pending": registrations.filter(
                    payment_verified=False
                ).count(),

                "revenue": (
                    registrations.filter(
                        payment_verified=True
                    ).aggregate(
                        total=Sum("price_paid")
                    )["total"] or 0
                ),

            },
        },
    )


# ==========================================================
# Dashboard Statistics Helper
# ==========================================================

def dashboard_statistics():

    registrations = CodingCampRegistration.objects

    return {

        "total": registrations.count(),

        "verified": registrations.filter(
            payment_verified=True
        ).count(),

        "pending": registrations.filter(
            payment_verified=False
        ).count(),

        "revenue": (
            registrations.filter(
                payment_verified=True
            ).aggregate(
                total=Sum("price_paid")
            )["total"] or 0
        ),

        "physical": registrations.filter(
            mode="PHYSICAL"
        ).count(),

        "virtual": registrations.filter(
            mode="VIRTUAL"
        ).count(),

        "completed": registrations.filter(
            registration_status="COMPLETED"
        ).count(),

        "waitlist": registrations.filter(
            registration_status="WAITLIST"
        ).count(),

    }
    
    
@staff_required
def sync_pending_registrations(request):

    result = RegistrationSyncService.sync_pending()

    if result["failed"] == 0:

        messages.success(

            request,

            f'{result["success"]} registration(s) synchronized successfully.'

        )

    else:

        messages.warning(

            request,

            (
                f'{result["success"]} synchronized, '
                f'{result["failed"]} failed.'
            ),

        )

    return redirect(
        "backoffice:dashboard"
    )

from django.views.generic import ListView
from django.utils.decorators import method_decorator

from teencamp.models import Batch


@method_decorator(staff_required, name="dispatch")
class BatchList(ListView):

    model = Batch

    template_name = "backoffice/batches.html"

    context_object_name = "batches"

    queryset = Batch.objects.order_by("priority", "id")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        batches = context["batches"]

        total_capacity = (
            batches.aggregate(total=Sum("capacity"))["total"] or 0
        )

        occupied_seats = (
            batches.aggregate(total=Sum("current_size"))["total"] or 0
        )

        context["total_capacity"] = total_capacity
        context["occupied_seats"] = occupied_seats
        context["available_seats"] = total_capacity - occupied_seats

        return context
    

@method_decorator(
    staff_required,
    name="dispatch",
)
class BatchUpdate(UpdateView):

    model = Batch

    form_class = BatchForm

    template_name = "backoffice/batch_form.html"

    def form_valid(self, form):

        messages.success(
            self.request,
            "Batch updated successfully."
        )

        return super().form_valid(form)

    def get_success_url(self):

        return reverse_lazy(
            "backoffice:batch-detail",
            kwargs={
                "pk": self.object.pk,
            },
        )
    

# ==========================================================
# End of File
# ==========================================================