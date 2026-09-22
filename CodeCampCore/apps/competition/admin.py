from django.contrib import admin
from .models import (
    CompetitionEdition,
    CompetitionSponsor,
    CompetitionJudge,
    CompetitionTeam,
    CompetitionParticipant,
    CompetitionCheckInLog,
    CompetitionScore,
)


@admin.action(description="Mark selected edition as active (deactivates others)")
def make_active(modeladmin, request, queryset):
    # Force only one active edition
    CompetitionEdition.objects.update(is_active=False)
    queryset.update(is_active=True)


@admin.register(CompetitionEdition)
class CompetitionEditionAdmin(admin.ModelAdmin):
    list_display = ('name', 'year', 'is_active', 'start_date', 'end_date')
    list_filter = ('is_active',)
    actions = [make_active]


@admin.register(CompetitionSponsor)
class CompetitionSponsorAdmin(admin.ModelAdmin):
    list_display = ('name', 'edition', 'tier', 'website')
    list_filter = ('edition', 'tier')
    search_fields = ('name',)


@admin.register(CompetitionJudge)
class CompetitionJudgeAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'edition', 'user', 'company', 'title')
    list_filter = ('edition',)
    search_fields = ('display_name', 'company', 'user__username')


@admin.register(CompetitionTeam)
class CompetitionTeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'edition', 'track', 'owner', 'join_code', 'created_at')
    list_filter = ('track', 'edition')
    search_fields = ('name', 'join_code', 'owner__username')


@admin.register(CompetitionParticipant)
class CompetitionParticipantAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'edition', 'email', 'track', 'team', 'checked_in', 'created_at')
    list_filter = ('track', 'edition', 'checked_in')
    search_fields = ('full_name', 'email', 'team__name')


@admin.register(CompetitionCheckInLog)
class CompetitionCheckInLogAdmin(admin.ModelAdmin):
    list_display = ('participant', 'edition', 'checked_by', 'timestamp')
    list_filter = ('edition', 'timestamp')
    search_fields = ('participant__full_name', 'checked_by__username')


@admin.register(CompetitionScore)
class CompetitionScoreAdmin(admin.ModelAdmin):
    list_display = ('participant', 'edition', 'judge', 'round', 'raw_score', 'normalized_score', 'created_at')
    list_filter = ('edition', 'round', 'raw_score')
    search_fields = ('participant__full_name', 'judge__username')
