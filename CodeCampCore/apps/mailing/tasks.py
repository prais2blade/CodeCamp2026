from django.core.mail import send_mail
from django.conf import settings
from .models import MailingList

def send_new_session_announcement(course_name, start_date):
    subject = f"New CodeCamp Session – {course_name} starts {start_date:%B %d}"
    message = (
        f"Hello! Registration is now open for the next {course_name} session, "
        f"starting {start_date:%B %d}. Visit our site to register today!"
    )
    for m in MailingList.objects.all():
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [m.email])
