from django.conf import settings
from django.core.mail import send_mail


class NotificationService:
    """
    Handles all outgoing notifications for CodeCamp.
    """

    @classmethod
    def registration_confirmed(cls, registration):
        """
        Send registration approval email.
        """

        subject = "CodeCamp Registration Approved"

        message = f"""
Dear {registration.parent_name},

Congratulations!

The registration for:

Student:
{registration.full_name}

has been approved successfully.

Registration Code:
{registration.reg_code}

Batch:
{registration.batch.name}

Reporting Time:
{registration.batch.reporting_time.strftime("%I:%M %p")}

Start Date:
{registration.batch.start_date.strftime("%d %B %Y")}

Venue:
CodeCamp Training Centre

We look forward to welcoming you.

Regards,

CodeCamp Team
""".strip()

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[registration.parent_email],
            fail_silently=False,
        )

    @classmethod
    def waitlisted(cls, registration):
        """
        Notify parent that student has been placed on the waiting list.
        """

        subject = "CodeCamp Waiting List"

        message = f"""
Dear {registration.parent_name},

Thank you for registering
{registration.full_name}.

All available batches are currently full.

Your child has been placed on our waiting list.

We will contact you immediately a space becomes available.

Regards,

CodeCamp Team
""".strip()

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[registration.parent_email],
            fail_silently=False,
        )

    @classmethod
    def parent_account_created(
        cls,
        registration,
        temporary_password,
    ):
        """
        Send Parent Portal login credentials.
        """

        subject = "Parent Portal Account Created"

        message = f"""
Dear {registration.parent_name},

A Parent Portal account has been created for you.

Phone Number:

{registration.parent_phone}

Temporary Password:

{temporary_password}

Please log in and change your password immediately.

Regards,

CodeCamp Team
""".strip()

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[registration.parent_email],
            fail_silently=False,
        )