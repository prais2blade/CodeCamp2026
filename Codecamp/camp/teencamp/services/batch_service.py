from teencamp.models import (
    Batch,
    CodingCampRegistration,
)


class BatchAllocationService:
    """
    Handles automatic batch allocation.

    Responsibility:
        - Decide which batch a registration should join.
        - Do NOT synchronize attendance.
        - Do NOT send notifications.
        - Do NOT increase batch occupancy.
    """

    @classmethod
    def allocate(cls, registration):
        """
        Determine the appropriate batch.

        Returns:
            Batch | None
        """

        if registration.mode == "VIRTUAL":
            return cls.allocate_virtual(registration)

        return cls.allocate_physical(registration)

    # =====================================================
    # Virtual Registration
    # =====================================================

    @classmethod
    def allocate_virtual(cls, registration):

        batch = Batch.objects.filter(
            mode="VIRTUAL",
            camp_year=registration.camp_year,
            is_active=True,
            accept_new_registrations=True,
        ).first()

        if batch:
            return batch

        registration.move_to_waitlist()

        registration.save(
            update_fields=[
                "registration_status",
            ]
        )

        return None

    # =====================================================
    # Physical Registration
    # =====================================================

    @classmethod
    def allocate_physical(cls, registration):

        # -------------------------------------------------
        # Rule 1:
        # Keep siblings in the same batch.
        # -------------------------------------------------

        parent_batch = cls.find_parent_batch(
            registration.parent_phone,
            registration.camp_year,
        )

        if (
            parent_batch
            and not parent_batch.reserved_for_existing_students
            and parent_batch.can_accept_registration()
        ):
            return parent_batch

        # -------------------------------------------------
        # Rule 2:
        # Allocate new family by priority.
        # -------------------------------------------------

        return cls.allocate_new_parent(registration)

    # =====================================================
    # New Parent Allocation
    # =====================================================

    @classmethod
    def allocate_new_parent(cls, registration):

        batches = Batch.objects.filter(
            mode="PHYSICAL",
            camp_year=registration.camp_year,
            is_active=True,
            accept_new_registrations=True,
            reserved_for_existing_students=False,
        ).order_by(
            "priority",
            "id",
        )

        for batch in batches:

            if batch.can_accept_registration():
                return batch

        registration.move_to_waitlist()

        registration.save(
            update_fields=[
                "registration_status",
            ]
        )

        return None

    # =====================================================
    # Find Existing Parent Batch
    # =====================================================

    @classmethod
    def find_parent_batch(
        cls,
        parent_phone,
        camp_year,
    ):

        previous_registration = (
            CodingCampRegistration.objects
            .select_related("batch")
            .filter(
                parent_phone=parent_phone,
                camp_year=camp_year,
                batch__isnull=False,
                registration_status__in=[
                    "BATCH_ASSIGNED",
                    "SYNC_PENDING",
                    "SYNCED",
                    "COMPLETED",
                ],
            )
            .first()
        )

        if previous_registration:
            return previous_registration.batch

        return None