from django.test import SimpleTestCase
from django.urls import reverse


class MailingUrlTests(SimpleTestCase):
    def test_join_mailing_list_has_single_prefix(self):
        self.assertEqual(reverse("join_mailing_list"), "/mailing/join/")
