from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse


class AccountFlowTests(TestCase):
    def test_health_endpoint_returns_ok(self):
        response = self.client.get(reverse("health_check"))

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content,
            {"status": "ok", "database": "available"},
        )

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_register_sends_verification_email_and_redirects(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "newstudent",
                "email": "student@example.com",
                "password": "safe-password-123",
                "confirm_password": "safe-password-123",
            },
        )

        self.assertRedirects(response, reverse("verify_email_sent"))
        self.assertTrue(User.objects.filter(username="newstudent").exists())
        self.assertEqual(len(mail.outbox), 1)

    def test_register_shows_error_when_username_already_exists(self):
        User.objects.create_user(
            username="newstudent",
            email="existing@example.com",
            password="safe-password-123",
        )

        response = self.client.post(
            reverse("register"),
            {
                "username": "newstudent",
                "email": "another@example.com",
                "password": "safe-password-123",
                "confirm_password": "safe-password-123",
            },
            follow=True,
        )

        self.assertContains(response, "Username already exists.")

    def test_finished_student_login_redirects_to_student_dashboard(self):
        user = User.objects.create_user(
            username="student1",
            email="student1@example.com",
            password="safe-password-123",
        )
        user.profile.is_verified = True
        user.profile.onboarding_stage = "finished"
        user.profile.role = "student"
        user.profile.save()

        response = self.client.post(
            reverse("login"),
            {"username": "student1", "password": "safe-password-123"},
        )

        self.assertRedirects(response, reverse("student_dashboard"))

    def test_complete_profile_page_renders_and_posts_to_role_dashboard(self):
        user = User.objects.create_user(
            username="student2",
            email="student2@example.com",
            password="safe-password-123",
        )
        user.profile.is_verified = True
        user.profile.onboarding_stage = "complete_profile"
        user.profile.role = "student"
        user.profile.save()
        self.client.force_login(user)

        get_response = self.client.get(reverse("complete_profile"))
        self.assertEqual(get_response.status_code, 200)

        post_response = self.client.post(reverse("complete_profile"), {"phone": "08000000000"})
        self.assertRedirects(post_response, reverse("student_dashboard"))

        user.profile.refresh_from_db()
        self.assertEqual(user.profile.onboarding_stage, "finished")

    def test_logout_is_allowed_while_onboarding_is_incomplete(self):
        user = User.objects.create_user(
            username="student3",
            email="student3@example.com",
            password="safe-password-123",
        )
        user.profile.is_verified = True
        user.profile.onboarding_stage = "welcome"
        user.profile.save()
        self.client.force_login(user)

        response = self.client.get(reverse("logout_user"))

        self.assertRedirects(response, reverse("login"))
