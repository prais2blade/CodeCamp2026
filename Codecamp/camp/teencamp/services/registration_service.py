from django.db import transaction

from teencamp.services.sync_dispatcher import SyncDispatcher
from teencamp.services.batch_service import BatchAllocationService
from teencamp.services.notification_service import NotificationService


class RegistrationService:
    """
    Coordinates the complete registration approval workflow.

    Workflow:

        1. Verify payment
        2. Allocate batch
        3. Assign registration
        4. Update batch occupancy
        5. Synchronize Attendance & CodeCampCore (SyncDispatcher)
        6. Send notification
        7. Complete registration
    """

    @classmethod
    @transaction.atomic
    def approve(cls, registration):

        # ============================================
        # STEP 1
        # Verify Payment
        # ============================================

        registration.approve_payment()

        registration.save(
            update_fields=[
                "payment_verified",
                "registration_status",
            ]
        )

        # ============================================
        # STEP 2
        # Find Appropriate Batch
        # ============================================

        batch = BatchAllocationService.allocate(
            registration
        )

        if batch is None:
            # Student has been moved to WAITLIST
            return registration

        # ============================================
        # STEP 3
        # Assign Batch
        # ============================================

        registration.assign_batch(batch)

        registration.save(
            update_fields=[
                "batch",
                "registration_status",
            ]
        )

        # ============================================
        # STEP 4
        # Update Batch Occupancy
        # ============================================

        batch.increment_size()

        # ============================================
        # STEP 5
        # Synchronize Attendance & CodeCampCore
        # ============================================

        SyncDispatcher.dispatch_all(registration)

        # ============================================
        # STEP 6
        # Send Confirmation
        # ============================================

        try:
            NotificationService.registration_confirmed(
                registration
            )
        except Exception as exc:
            pass

        return registration