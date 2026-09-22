from django.db import models

class MailingList(models.Model):
    email = models.EmailField(unique=True)
    date_added = models.DateTimeField(auto_now_add=True)
    notified_sessions = models.IntegerField(default=0)

    def __str__(self):
        return self.email
