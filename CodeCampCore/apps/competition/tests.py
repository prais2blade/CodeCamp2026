from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import CompetitionEdition, CompetitionParticipant, CompetitionTeam


class CompetitionFlowTests(TestCase):
    def setUp(self):
        self.edition = CompetitionEdition.objects.create(
            year=2026,
            name="CRACKdaCODE 2026",
            is_active=True,
            start_date=timezone.now(),
        )

    def test_competition_track_defaults_match_choices(self):
        team_default = CompetitionTeam._meta.get_field("track").default
        participant_default = CompetitionParticipant._meta.get_field("track").default
        valid_choices = dict(CompetitionTeam.TRACK_CHOICES)

        self.assertIn(team_default, valid_choices)
        self.assertIn(participant_default, valid_choices)

    def test_competition_login_page_renders(self):
        response = self.client.get(reverse("competition:login", kwargs={"year": self.edition.year}))
        self.assertEqual(response.status_code, 200)

    def test_competition_dashboard_renders_for_participant(self):
        user = User.objects.create_user(
            username="competitor",
            email="competitor@example.com",
            password="safe-password-123",
        )
        CompetitionParticipant.objects.create(
            edition=self.edition,
            user=user,
            full_name="Competition User",
            email="competitor@example.com",
            track="python",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("competition:dashboard", kwargs={"year": self.edition.year}))

        self.assertEqual(response.status_code, 200)

    def test_judge_dashboard_renders_for_staff(self):
        staff_user = User.objects.create_user(
            username="judgeuser",
            email="judge@example.com",
            password="safe-password-123",
            is_staff=True,
        )
        participant_user = User.objects.create_user(
            username="participantuser",
            email="participant@example.com",
            password="safe-password-123",
        )
        CompetitionParticipant.objects.create(
            edition=self.edition,
            user=participant_user,
            full_name="Participant User",
            email="participant@example.com",
            track="javascripts",
        )
        self.client.force_login(staff_user)

        response = self.client.get(reverse("competition:judge_dashboard", kwargs={"year": self.edition.year}))

        self.assertEqual(response.status_code, 200)

    def test_staff_checkin_page_renders_for_staff(self):
        staff_user = User.objects.create_user(
            username="staffcheckin",
            email="staff@example.com",
            password="safe-password-123",
            is_staff=True,
        )
        participant_user = User.objects.create_user(
            username="staffparticipant",
            email="staffparticipant@example.com",
            password="safe-password-123",
        )
        CompetitionParticipant.objects.create(
            edition=self.edition,
            user=participant_user,
            full_name="Staff Participant",
            email="staffparticipant@example.com",
            track="python",
        )
        self.client.force_login(staff_user)

        response = self.client.get(reverse("competition:staff_checkin", kwargs={"year": self.edition.year}))

        self.assertEqual(response.status_code, 200)
