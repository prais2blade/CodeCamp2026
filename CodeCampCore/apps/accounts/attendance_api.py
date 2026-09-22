import json
import secrets

from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.courses.models import Subject
from apps.scheduling.models import Batch

from .models import Attendance, Profile


STATUS_MAP = {
    "present": "Present",
    "p": "Present",
    "1": "Present",
    "true": "Present",
    "absent": "Absent",
    "a": "Absent",
    "0": "Absent",
    "false": "Absent",
    "late": "Late",
    "l": "Late",
    "excused": "Excused",
    "e": "Excused",
}


def _provided_api_key(request):
    auth_header = request.headers.get("Authorization", "") or request.META.get("HTTP_AUTHORIZATION", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1].strip()
    return (
        request.headers.get("X-Attendance-Key", "")
        or request.headers.get("X-API-KEY", "")
        or request.META.get("HTTP_X_ATTENDANCE_KEY", "")
        or request.META.get("HTTP_X_API_KEY", "")
    ).strip()


def _resolve_student(record):
    User = get_user_model()
    queryset = User.objects.select_related("profile")

    external_id = str(record.get("external_student_id") or record.get("external_id") or "").strip()
    if external_id:
        profile = Profile.objects.select_related("user").filter(
            external_attendance_id=external_id
        ).first()
        if profile:
            return profile.user

    user_id = record.get("user_id") or record.get("student_id")
    if user_id and str(user_id).isdigit():
        user = queryset.filter(id=int(user_id)).first()
        if user:
            return user

    if user_id and str(user_id).strip():
        profile = Profile.objects.select_related("user").filter(
            external_attendance_id=str(user_id).strip()
        ).first()
        if profile:
            return profile.user

    username = str(record.get("student_username") or record.get("username") or "").strip()
    if username:
        user = queryset.filter(username=username).first()
        if user:
            return user

    email = str(record.get("student_email") or record.get("email") or "").strip()
    if email:
        user = queryset.filter(email__iexact=email).first()
        if user:
            return user

    raise ValueError("Student not found. Send external_student_id, student_id, username, or email.")


def _resolve_subject(record, student):
    subject_id = record.get("subject_id")
    if subject_id:
        subject = Subject.objects.select_related("course").filter(id=subject_id).first()
        if subject:
            return subject

    subject_name = str(record.get("subject_name") or record.get("subject") or "").strip()
    course = getattr(student.profile, "course", None)

    if subject_name:
        subjects = Subject.objects.select_related("course").filter(name__iexact=subject_name)
        if course:
            subjects = subjects.filter(course=course)
        subject = subjects.first()
        if subject:
            return subject

    # Fallback: if student has a course, use the first subject or create default
    if course:
        first_subject = course.subjects.first()
        if first_subject:
            return first_subject
        # Create a default general subject for this course
        return Subject.objects.create(course=course, name="General Attendance")

    # If no course assigned on profile, check if there is any default course
    default_course = Course.objects.first()
    if default_course:
        first_subject = default_course.subjects.first()
        if first_subject:
            return first_subject
        return Subject.objects.create(course=default_course, name="General Attendance")

    raise ValueError("Subject not found and no course is assigned to student profile.")


def _resolve_batch(record, student, subject):
    batch_id = record.get("batch_id")
    if batch_id:
        batch = Batch.objects.select_related("course").filter(id=batch_id).first()
        if not batch:
            raise ValueError("Batch not found.")
        return batch

    batch_name = str(record.get("batch_name") or record.get("batch") or "").strip()
    if batch_name:
        batch = Batch.objects.select_related("course").filter(
            name__iexact=batch_name,
            course=subject.course,
        ).first()
        if batch:
            return batch

    return getattr(student.profile, "batch", None)


def _parse_attendance_date(record):
    raw_value = record.get("date") or record.get("attendance_date")
    if not raw_value:
        return timezone.localdate()

    value = str(raw_value).strip()
    parsed_date = parse_date(value)
    if parsed_date:
        return parsed_date

    parsed_datetime = parse_datetime(value)
    if parsed_datetime:
        return timezone.localtime(parsed_datetime).date() if timezone.is_aware(parsed_datetime) else parsed_datetime.date()

    raise ValueError("Invalid date. Use YYYY-MM-DD or an ISO datetime.")


def _normalize_status(record):
    raw_status = str(record.get("status") or "present").strip().lower()
    status = STATUS_MAP.get(raw_status)
    if not status:
        raise ValueError("Invalid status. Use Present, Absent, Late, or Excused.")
    return status


def _resolve_marker(record):
    username = str(record.get("marked_by_username") or "").strip()
    if not username:
        return None

    User = get_user_model()
    return User.objects.filter(username=username).first()


def _sync_one(record):
    student = _resolve_student(record)
    profile = student.profile
    if profile.role != "student":
        raise ValueError("Attendance can only be recorded for student profiles.")

    subject = _resolve_subject(record, student)
    batch = _resolve_batch(record, student, subject)
    attendance_date = _parse_attendance_date(record)
    status = _normalize_status(record)

    remarks = record.get("remarks", "")
    check_in = record.get("check_in")
    check_out = record.get("check_out")
    
    parsed_check_in = None
    parsed_check_out = None
    if check_in:
        from django.utils.dateparse import parse_time
        parsed_check_in = parse_time(str(check_in).strip())
    if check_out:
        from django.utils.dateparse import parse_time
        parsed_check_out = parse_time(str(check_out).strip())

    if check_in or check_out:
        time_info = f"In: {check_in or 'N/A'}, Out: {check_out or 'N/A'}"
        remarks = f"{remarks} [{time_info}]".strip() if remarks else time_info

    tenant = getattr(profile, "tenant", None)

    attendance, created = Attendance.objects.update_or_create(
        student=student,
        subject=subject,
        date=attendance_date,
        defaults={
            "tenant": tenant,
            "batch": batch,
            "status": status,
            "check_in_time": parsed_check_in,
            "check_out_time": parsed_check_out,
            "marked_by": _resolve_marker(record),
            "remarks": remarks,
            "source": str(record.get("source") or "external_kiosk")[:50],
            "external_reference": str(record.get("external_reference") or record.get("external_ref") or "")[:100],
            "synced_at": timezone.now(),
        },
    )

    return {
        "id": attendance.id,
        "student_id": student.id,
        "external_student_id": profile.external_attendance_id,
        "subject_id": subject.id,
        "batch_id": batch.id if batch else None,
        "date": attendance.date.isoformat(),
        "status": attendance.status,
        "created": created,
    }


@csrf_exempt
@require_POST
def sync_attendance(request):
    provided = _provided_api_key(request)
    if not provided:
        return JsonResponse({"error": "Attendance API key required."}, status=401)

    # 1. Check Tenant-specific API Keys
    tenant_matched = False
    try:
        from apps.tenants.models import TenantAPIKey
        from apps.tenants.context import set_current_tenant
        tenant_key = TenantAPIKey.objects.select_related("tenant").filter(
            key=provided,
            is_active=True,
            tenant__is_active=True,
        ).first()
        if tenant_key:
            tenant_key.last_used_at = timezone.now()
            tenant_key.save(update_fields=["last_used_at"])
            request.tenant = tenant_key.tenant
            set_current_tenant(tenant_key.tenant)
            tenant_matched = True
    except Exception:
        pass

    # 2. Check Master static keys
    if not tenant_matched:
        valid_keys = [
            k for k in [
                getattr(settings, "ATTENDANCE_API_KEY", ""),
                getattr(settings, "CORE_API_KEY", ""),
                getattr(settings, "REGISTRATION_API_KEY", ""),
            ] if k
        ]

        if not valid_keys:
            return JsonResponse(
                {"error": "ATTENDANCE_API_KEY / CORE_API_KEY is not configured."},
                status=503,
            )

        matched = any(secrets.compare_digest(k, provided) for k in valid_keys)
        if not matched:
            return JsonResponse({"error": "Invalid attendance API key."}, status=403)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body."}, status=400)

    records = payload.get("records", payload)
    if isinstance(records, dict):
        records = [records]
    if not isinstance(records, list) or not records:
        return JsonResponse({"error": "Send a record object or a non-empty records list."}, status=400)

    synced = []
    errors = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            errors.append({"index": index, "error": "Record must be an object."})
            continue
        try:
            synced.append(_sync_one(record))
        except ValueError as exc:
            errors.append({"index": index, "error": str(exc)})

    status_code = 200
    if errors and synced:
        status_code = 207
    elif errors:
        status_code = 400

    return JsonResponse(
        {
            "success": len(errors) == 0,
            "synced": synced,
            "errors": errors,
            "synced_count": len(synced),
            "error_count": len(errors),
        },
        status=status_code,
    )
