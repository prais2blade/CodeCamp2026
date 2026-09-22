from django.db import transaction

from teencamp.models import (
    CodingCampRegistration,
    STANDARD_PRICE,
    DISCOUNT_RATE,
    EARLY_BIRD_LIMIT,
)


class RegistrationSubmissionService:
    """
    Handles creation of new CodeCamp registrations.
    """

    @classmethod
    @transaction.atomic
    def submit(cls, form):

        cleaned_data = form.cleaned_data

        # ---------------------------------------------
        # Prevent duplicate child registration
        # ---------------------------------------------
        if CodingCampRegistration.objects.select_for_update().filter(
            first_name=cleaned_data["first_name"],
            last_name=cleaned_data["last_name"],
            parent_phone=cleaned_data["parent_phone"],
            camp_year=cleaned_data.get("camp_year")
                or CodingCampRegistration._meta.get_field("camp_year").default,
        ).exists():

            raise ValueError(
                "This student has already been registered."
            )

        registration = form.save(commit=False)

        total = (
            CodingCampRegistration.objects
            .select_for_update()
            .count()
        )

        registration.discount_applied = (
            total < EARLY_BIRD_LIMIT
        )

        registration.price_paid = (
            STANDARD_PRICE * (1 - DISCOUNT_RATE)
            if registration.discount_applied
            else STANDARD_PRICE
        )

        registration.payment_verified = False
        registration.registration_status = "PENDING"

        # Batch assignment happens AFTER payment approval
        registration.batch = None

        registration.save()

        return registration