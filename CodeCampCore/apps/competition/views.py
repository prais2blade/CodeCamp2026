from io import BytesIO
import random
import string
from datetime import datetime

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Avg
from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

import qrcode
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from .forms import (
    CompetitionLoginForm,
    CompetitionRegistrationForm,
    JudgeScoreForm,
    TeamCreateForm,
    TeamJoinForm,
)
from .models import (
    CompetitionCheckInLog,
    CompetitionEdition,
    CompetitionJudge,
    CompetitionParticipant,
    CompetitionScore,
    CompetitionSponsor,
    CompetitionTeam,
)
from django.db.models import Avg, F, FloatField, ExpressionWrapper, Value
from django.db.models.functions import Coalesce
from django.shortcuts import render, get_object_or_404
from .models import CompetitionParticipant, CompetitionEdition

User = get_user_model()


# ---------- helpers ----------

def get_active_edition():
    edition = CompetitionEdition.objects.filter(is_active=True).order_by('-year').first()
    if not edition and hasattr(settings, 'COMPETITION_DEFAULT_YEAR'):
        edition = CompetitionEdition.objects.filter(year=settings.COMPETITION_DEFAULT_YEAR).first()
    return edition


def get_edition_or_404(year: int):
    try:
        return CompetitionEdition.objects.get(year=year)
    except CompetitionEdition.DoesNotExist:
        raise Http404("Edition not found")


def ensure_global_active():
    if not getattr(settings, 'COMPETITION_GLOBAL_ACTIVE', True):
        return False
    return True


# ---------- root & archive ----------

def root_redirect(request):
    if not ensure_global_active():
        return render(request, 'competition/closed.html')

    edition = get_active_edition()
    if not edition:
        return render(request, 'competition/closed.html')
    return redirect('competition:home', year=edition.year)


def archive(request):
    editions = CompetitionEdition.objects.all()
    return render(request, 'competition/archive.html', {
        'editions': editions,
    })


# ---------- public pages (per edition) ----------

def home(request, year):
    if not ensure_global_active():
        return render(request, 'competition/closed.html')

    edition = get_edition_or_404(year)
    start_iso = edition.start_date.isoformat() if edition.start_date else None
    registration_open = edition.is_active  # simple rule: active => registration open; you can refine later

    return render(request, 'competition/home.html', {
        'edition': edition,
        'competition_start_iso': start_iso,
        'registration_open': registration_open,
    })


def about(request, year):
    edition = get_edition_or_404(year)
    return render(request, 'competition/about.html', {'edition': edition})


def categories(request, year):
    edition = get_edition_or_404(year)
    return render(request, 'competition/categories.html', {'edition': edition})


def judges(request, year):
    edition = get_edition_or_404(year)
    judges_qs = CompetitionJudge.objects.filter(edition=edition)
    return render(request, 'competition/judges.html', {
        'edition': edition,
        'judges': judges_qs,
    })


def gallery(request, year):
    edition = get_edition_or_404(year)
    return render(request, 'competition/gallery.html', {'edition': edition})


def sponsors(request, year):
    edition = get_edition_or_404(year)
    sponsors_qs = CompetitionSponsor.objects.filter(edition=edition)
    return render(request, 'competition/sponsors.html', {
        'edition': edition,
        'sponsors': sponsors_qs,
    })


def contact(request, year):
    edition = get_edition_or_404(year)
    return render(request, 'competition/contact.html', {'edition': edition})


def schedule(request, year):
    edition = get_edition_or_404(year)
    return render(request, 'competition/schedule.html', {'edition': edition})


def rules(request, year):
    edition = get_edition_or_404(year)
    return render(request, 'competition/rules.html', {'edition': edition})


def prizes(request, year):
    edition = get_edition_or_404(year)
    return render(request, 'competition/prizes.html', {'edition': edition})


def closed_view(request):
    return render(request, 'competition/closed.html')


# ---------- registration / auth / dashboard ----------

def register(request, year):
    if not ensure_global_active():
        return render(request, 'competition/closed.html')

    edition = get_edition_or_404(year)
    if not edition.is_active:
        return render(request, 'competition/registration_closed.html', {'edition': edition})

    if request.method == 'POST':
        form = CompetitionRegistrationForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            full_name = form.cleaned_data['full_name']
            phone = form.cleaned_data['phone']
            track = form.cleaned_data['track']

            user = User.objects.create_user(
                username=username,
                email=email,
                password=password
            )

            CompetitionParticipant.objects.create(
                edition=edition,
                user=user,
                full_name=full_name,
                email=email,
                phone=phone,
                track=track
            )

            messages.success(request, "Registration successful. Please log in.")
            return redirect('competition:login', year=edition.year)
    else:
        form = CompetitionRegistrationForm()

    return render(request, 'competition/register.html', {
        'edition': edition,
        'form': form,
    })


def login_view(request, year):
    edition = get_edition_or_404(year)
    if request.method == 'POST':
        form = CompetitionLoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            pwd = form.cleaned_data['password']
            user = authenticate(request, username=username, password=pwd)
            if user is not None:
                login(request, user)
                return redirect('competition:dashboard', year=edition.year)
            messages.error(request, "Invalid username or password.")
    else:
        form = CompetitionLoginForm()
    return render(request, 'competition/login.html', {
        'edition': edition,
        'form': form,
    })


def logout_view(request, year):
    logout(request)
    return redirect('competition:home', year=year)


@login_required
def dashboard(request, year):
    edition = get_edition_or_404(year)
    participant = CompetitionParticipant.objects.filter(user=request.user, edition=edition).first()
    team_create_form = None
    team_join_form = None

    if participant:
        team_create_form = TeamCreateForm(initial={'track': participant.track})
        team_join_form = TeamJoinForm()

    return render(request, 'competition/dashboard.html', {
        'edition': edition,
        'participant': participant,
        'team_create_form': team_create_form,
        'team_join_form': team_join_form,
    })


@login_required
def qr_code_image(request, year, participant_id):
    edition = get_edition_or_404(year)
    participant = get_object_or_404(
        CompetitionParticipant,
        id=participant_id,
        user=request.user,
        edition=edition
    )
    data = f'competition_participant:{edition.year}:{participant.id}:email:{participant.email}'
    img = qrcode.make(data)
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return HttpResponse(buffer.getvalue(), content_type='image/png')


@login_required
def ticket_pdf(request, year):
    edition = get_edition_or_404(year)
    participant = CompetitionParticipant.objects.filter(user=request.user, edition=edition).first()
    if not participant:
        return HttpResponse("No participant profile found for this edition.", status=404)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="ticket_{edition.year}_{participant.id}.pdf"'

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    qr_data = f'competition_ticket:{edition.year}:{participant.id}:{participant.email}'
    qr_img = qrcode.make(qr_data)
    qr_io = BytesIO()
    qr_img.save(qr_io, format='PNG')
    qr_io.seek(0)
    qr_reader = ImageReader(qr_io)

    p.setFont("Helvetica-Bold", 18)
    p.drawString(40 * mm, (height - 40 * mm), f"CRACKdaCODE PASS - {edition.year}")

    p.setFont("Helvetica", 12)
    p.drawString(40 * mm, (height - 50 * mm), f"Edition: {edition.name}")
    p.drawString(40 * mm, (height - 58 * mm), f"Name: {participant.full_name}")
    p.drawString(40 * mm, (height - 66 * mm), f"Track: {participant.get_track_display()}")
    if participant.team:
        p.drawString(40 * mm, (height - 74 * mm), f"Team: {participant.team.name}")
    else:
        p.drawString(40 * mm, (height - 74 * mm), "Team: Solo")

    p.drawString(40 * mm, (height - 82 * mm), "Signature: __________________________")

    qr_size = 60 * mm
    p.drawImage(
        qr_reader,
        width - 40 * mm - qr_size,
        height - 40 * mm - qr_size,
        qr_size,
        qr_size,
    )

    p.showPage()
    p.save()

    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)
    return response


# ---------- team management ----------

def _generate_join_code(length=8):
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


@login_required
def team_create(request, year):
    edition = get_edition_or_404(year)
    participant = CompetitionParticipant.objects.filter(user=request.user, edition=edition).first()
    if not participant:
        messages.error(request, "You must be a competition participant to create a team.")
        return redirect('competition:dashboard', year=edition.year)

    if request.method == 'POST':
        form = TeamCreateForm(request.POST)
        if form.is_valid():
            team = form.save(commit=False)
            team.owner = request.user
            team.edition = edition

            while True:
                code = _generate_join_code()
                if not CompetitionTeam.objects.filter(join_code=code).exists():
                    team.join_code = code
                    break
            team.save()

            participant.team = team
            participant.track = team.track
            participant.save()
            messages.success(request, f"Team '{team.name}' created. Join code: {team.join_code}")
    return redirect('competition:dashboard', year=edition.year)


@login_required
def team_join(request, year):
    edition = get_edition_or_404(year)
    participant = CompetitionParticipant.objects.filter(user=request.user, edition=edition).first()
    if not participant:
        messages.error(request, "You must be a competition participant to join a team.")
        return redirect('competition:dashboard', year=edition.year)

    if request.method == 'POST':
        form = TeamJoinForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data['join_code'].strip().upper()
            team = CompetitionTeam.objects.filter(join_code=code, edition=edition).first()
            if not team:
                messages.error(request, "Invalid join code.")
            else:
                # enforce team size limit
                current_members = team.members.count()
                if current_members >= edition.max_team_size:
                    messages.error(request, f"This team is full (max {edition.max_team_size} members).")
                else:
                    participant.team = team
                    participant.track = team.track
                    participant.save()
                    messages.success(request, f"You joined team '{team.name}'.")
    return redirect('competition:dashboard', year=edition.year)


# ---------- staff check-in ----------

@staff_member_required
def staff_checkin(request, year):
    edition = get_edition_or_404(year)
    q = request.GET.get('q', '')
    participants = CompetitionParticipant.objects.filter(edition=edition).order_by('-created_at')
    if q:
        participants = participants.filter(full_name__icontains=q)
    return render(request, 'competition/checkin_staff.html', {
        'edition': edition,
        'participants': participants,
        'query': q,
    })


@staff_member_required
def do_checkin(request, year, pk):
    edition = get_edition_or_404(year)
    participant = get_object_or_404(CompetitionParticipant, pk=pk, edition=edition)
    participant.checked_in = True
    participant.save()
    CompetitionCheckInLog.objects.create(edition=edition, participant=participant, checked_by=request.user)
    messages.success(request, f'{participant.full_name} checked in.')
    return redirect('competition:staff_checkin', year=edition.year)


@staff_member_required
def search_participant(request, year):
    edition = get_edition_or_404(year)
    q = request.GET.get('q', '')
    participants = CompetitionParticipant.objects.filter(
        edition=edition,
        full_name__icontains=q
    )[:50]
    return render(request, 'competition/checkin_search_results.html', {
        'edition': edition,
        'participants': participants,
        'query': q,
    })


# ---------- leaderboard & judges ----------

def leaderboard(request, year):
    edition = get_object_or_404(CompetitionEdition, year=year)

    # Get all participants for this edition
    qs = CompetitionParticipant.objects.filter(
        edition=edition
    ).select_related('team', 'user')

    # Compute avg raw score (NULL → 0)
    avg_raw_expr = Coalesce(Avg('scores__raw_score'), Value(0.0))

    qs = qs.annotate(
        avg_raw=avg_raw_expr
    )

    # Compute normalized score in DB: raw_score * 10
    qs = qs.annotate(
        avg_norm=ExpressionWrapper(
            F('avg_raw') * Value(10.0),
            output_field=FloatField()
        )
    )

    # Order by normalized score DESC
    qs = qs.order_by('-avg_norm', 'full_name')

    return render(request, 'competition/leaderboard.html', {
        'edition': edition,
        'participants': qs,
    })


@staff_member_required
def judge_dashboard(request, year):
    edition = get_edition_or_404(year)
    participants = CompetitionParticipant.objects.filter(edition=edition).order_by('track', 'full_name')
    return render(request, 'competition/judge_dashboard.html', {
        'edition': edition,
        'participants': participants,
    })


@staff_member_required
def judge_score(request, year, participant_id):
    edition = get_edition_or_404(year)
    participant = get_object_or_404(CompetitionParticipant, id=participant_id, edition=edition)
    score_obj = CompetitionScore.objects.filter(
        participant=participant,
        judge=request.user
    ).first()

    if request.method == 'POST':
        form = JudgeScoreForm(request.POST, instance=score_obj)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.edition = edition
            obj.participant = participant
            obj.judge = request.user
            obj.save()
            messages.success(request, f"Score saved for {participant.full_name}.")
            return redirect('competition:judge_dashboard', year=edition.year)
    else:
        form = JudgeScoreForm(instance=score_obj)

    return render(request, 'competition/judge_score.html', {
        'edition': edition,
        'participant': participant,
        'form': form,
    })
