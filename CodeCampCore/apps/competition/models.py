from django.db import models
from django.conf import settings


class CompetitionEdition(models.Model):
    year = models.IntegerField(unique=True)
    name = models.CharField(max_length=200)
    is_active = models.BooleanField(default=False)

    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)

    # Edition-level config:
    min_team_size = models.PositiveIntegerField(default=1)
    max_team_size = models.PositiveIntegerField(default=4)

    # For schedule / rules / prizes pages (simple text blobs you can fill from admin)
    schedule_markdown = models.TextField(blank=True)
    rules_markdown = models.TextField(blank=True)
    prizes_markdown = models.TextField(blank=True)
    theme = models.CharField(
        max_length=20,
        default="default",
        choices=[
            ("default", "Default Theme"),
            ("punk", "Hackathon Punk Theme"),
        ]
    )


    # Email template for reminders
    reminder_subject = models.CharField(max_length=200, blank=True)
    reminder_body = models.TextField(
        blank=True,
        help_text="Use {full_name} for participant name placeholders."
    )

    class Meta:
        ordering = ['-year']

    def __str__(self):
        return f"{self.name} ({self.year})"


class CompetitionSponsor(models.Model):
    edition = models.ForeignKey(CompetitionEdition, on_delete=models.CASCADE, related_name='sponsors')
    name = models.CharField(max_length=200)
    tier = models.CharField(max_length=50, blank=True)  # Bronze / Silver / Gold, etc.
    logo = models.ImageField(upload_to='competition/sponsors/', blank=True, null=True)
    website = models.URLField(blank=True)

    def __str__(self):
        return f"{self.name} [{self.edition}]"


class CompetitionJudge(models.Model):
    edition = models.ForeignKey(CompetitionEdition, on_delete=models.CASCADE, related_name='judges')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    display_name = models.CharField(max_length=200)
    bio = models.TextField(blank=True)
    title = models.CharField(max_length=200, blank=True)
    company = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"{self.display_name} - {self.edition}"


class CompetitionTeam(models.Model):
    TRACK_CHOICES = [
        ('javascripts', 'JavaScript'),
        ('python', 'Python'),        
    ]

    edition = models.ForeignKey(CompetitionEdition, on_delete=models.CASCADE, related_name='teams')
    name = models.CharField(max_length=200)
    track = models.CharField(max_length=50, choices=TRACK_CHOICES, default='javascripts')
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    join_code = models.CharField(max_length=12, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.get_track_display()})"


class CompetitionParticipant(models.Model):
    TRACK_CHOICES = CompetitionTeam.TRACK_CHOICES

    edition = models.ForeignKey(CompetitionEdition, on_delete=models.CASCADE, related_name='participants')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)

    team = models.ForeignKey(
        CompetitionTeam,
        related_name='members',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    track = models.CharField(max_length=50, choices=TRACK_CHOICES, default='javascripts')
    checked_in = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'edition')

    def __str__(self):
        return f"{self.full_name} ({self.edition.year} - {self.track})"


class CompetitionCheckInLog(models.Model):
    edition = models.ForeignKey(CompetitionEdition, on_delete=models.CASCADE, related_name='checkins')
    participant = models.ForeignKey(CompetitionParticipant, on_delete=models.CASCADE)
    checked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.participant} at {self.timestamp}"


class CompetitionScore(models.Model):
    ROUND_CHOICES = [
        ('r1', 'Round 1'),
        ('r2', 'Round 2'),
        ('final', 'Final'),
    ]

    edition = models.ForeignKey(CompetitionEdition, on_delete=models.CASCADE, related_name='scores')
    participant = models.ForeignKey(
        CompetitionParticipant,
        related_name='scores',
        on_delete=models.CASCADE
    )
    judge = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    round = models.CharField(max_length=10, choices=ROUND_CHOICES, default='r1')
    raw_score = models.PositiveIntegerField()
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('participant', 'judge', 'round')

    def __str__(self):
        return f"{self.participant} - {self.raw_score} by {self.judge} ({self.round})"

    @property
    def normalized_score(self):
        # normalise from 0–100 assuming judge uses 0–10 scale; adjust as needed
        return min(self.raw_score * 10, 100)
