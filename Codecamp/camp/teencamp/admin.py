from django.contrib import admin

from teencamp.models import (
    Batch,
    CodingCampRegistration,
)

from teencamp.services.registration_service import (
    RegistrationService,
)


# ==========================================================
# Batch Admin
# ==========================================================

@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):

    list_display = (
        "code",
        "name",
        "mode",
        "camp_year",
        "capacity",
        "current_size",
        "remaining_seats",
        "priority",
        "reserved_for_existing_students",
        "is_active",
    )

    list_filter = (
        "mode",
        "camp_year",
        "reserved_for_existing_students",
        "is_active",
        "accept_new_registrations",
    )

    search_fields = (
        "code",
        "name",
    )

    ordering = (
        "priority",
        "code",
    )

    readonly_fields = (
        "current_size",
        "remaining_seats",
    )

    fieldsets = (

        (
            "Batch Information",
            {
                "fields": (
                    ("code", "name"),
                    ("mode", "camp_year"),
                    ("capacity", "current_size"),
                    "priority",
                    "accept_new_registrations",
                    "is_active",
                )
            },
        ),

        (
            "Schedule",
            {
                "fields": (
                    "class_days",
                    "reporting_time",
                    ("start_date", "end_date"),
                )
            },
        ),
    )


# ==========================================================
# Registration Admin
# ==========================================================

@admin.register(CodingCampRegistration)
class CodingCampRegistrationAdmin(admin.ModelAdmin):

    list_display = (
        "reg_code",
        "student_name",
        "parent_name",
        "mode",
        "batch",
        "registration_status",
        "payment_verified",
        "attendance_synced",
        "created_at",
    )

    list_filter = (
        "mode",
        "registration_status",
        "payment_verified",
        "attendance_synced",
        "batch",
        "camp_year",
    )

    search_fields = (
        "reg_code",
        "reference",
        "first_name",
        "last_name",
        "parent_name",
        "parent_phone",
        "parent_email",
    )

    ordering = (
        "-created_at",
    )

    readonly_fields = (
        "reference",
        "reg_code",
        "attendance_student_id",
        "attendance_sync_date",
        "created_at",
        "updated_at",
    )

    fieldsets = (

        (
            "Student Information",
            {
                "fields": (
                    ("first_name", "last_name"),
                    "age",
                    "mode",
                )
            },
        ),

        (
            "Parent Information",
            {
                "fields": (
                    "parent_name",
                    "relationship",
                    ("parent_phone", "parent_whatsapp"),
                    "parent_email",
                )
            },
        ),

        (
            "Payment",
            {
                "fields": (
                    "discount_applied",
                    "price_paid",
                    "receipt",
                    "payment_verified",
                )
            },
        ),

        (
            "Registration",
            {
                "fields": (
                    "registration_status",
                    "batch",
                    "camp_year",
                    "reference",
                    "reg_code",
                )
            },
        ),

        (
            "Attendance Synchronization",
            {
                "fields": (
                    "attendance_synced",
                    "attendance_student_id",
                    "attendance_sync_date",
                )
            },
        ),

        (
            "Metadata",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    actions = (
        "approve_registration",
    )

    # ------------------------------------------------------
    # Display Helpers
    # ------------------------------------------------------

    @admin.display(description="Student")
    def student_name(self, obj):
        return obj.full_name

    # ------------------------------------------------------
    # Admin Actions
    # ------------------------------------------------------

    @admin.action(description="Approve selected registrations")
    def approve_registration(
        self,
        request,
        queryset,
    ):

        successful = 0
        failed = 0

        for registration in queryset:

            try:

                RegistrationService.approve(
                    registration
                )

                successful += 1

            except Exception as exc:

                failed += 1

                self.message_user(
                    request,
                    f"{registration.reg_code}: {exc}",
                    level="ERROR",
                )

        if successful:

            self.message_user(
                request,
                f"{successful} registration(s) approved successfully.",
            )

        if failed:

            self.message_user(
                request,
                f"{failed} registration(s) failed.",
                level="WARNING",
            )