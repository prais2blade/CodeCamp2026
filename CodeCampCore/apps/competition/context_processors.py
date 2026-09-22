from apps.competition.models import CompetitionEdition

def current_edition(request):
    try:
        return {
            "edition": CompetitionEdition.objects.filter(is_active=True).first()
        }
    except:
        return {"edition": None}
