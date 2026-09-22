from .models import Notification

from .services import send_notification_email, send_whatsapp_message



def process_pending_notifications():

    notifications = Notification.objects.filter(

        status="pending"

    )

    for notification in notifications:

        if notification.channel == "email":

            send_notification_email(
                notification
            )

        elif notification.channel == "whatsapp":

            success = send_whatsapp_message(

                notification.recipient,

                notification.message

            )

            if success:

                notification.status = "sent"

                notification.save(

                    update_fields=[
                        "status"
                    ]

                )