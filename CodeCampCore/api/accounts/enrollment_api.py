from decimal import Decimal
import secrets
from django.contrib.auth import get_user_model
from django.db import models, transaction
from django.utils import timezone
from django.utils.text import slugify
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from api.authentication import CoreAPIKeyAuthentication
from apps.accounts.models import Profile
from apps.courses.models import Course
from apps.payments.models import Payment, Receipt
from apps.scheduling.models import Batch
from apps.tenants.context import get_current_tenant


class StudentEnrollmentSyncAPIView(APIView):
    """
    Inbound enrollment ingestion API for CodeCamp admissions.
    Accepts single student registration or batch registrations from Codecamp.
    """

    authentication_classes = [CoreAPIKeyAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        payload = request.data
        if not isinstance(payload, dict):
            return Response(
                {"error": "Payload must be a JSON object."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        records = payload.get("records")
        if records and isinstance(records, list):
            results = []
            for record in records:
                res = self._process_single_enrollment(record)
                results.append(res)
            return Response({"success": True, "results": results}, status=status.HTTP_200_OK)

        res = self._process_single_enrollment(payload)
        return Response(res, status=status.HTTP_200_OK if not res.get("created") else status.HTTP_201_CREATED)

    def _process_single_enrollment(self, data):
        User = get_user_model()

        first_name = (data.get("first_name") or "").strip()
        last_name = (data.get("last_name") or "").strip()
        email = (data.get("email") or data.get("student_email") or data.get("parent_email") or "").strip().lower()
        phone = (data.get("phone") or data.get("parent_phone") or "").strip()
        reg_code = (data.get("registration_code") or data.get("reg_code") or "").strip()
        external_id = (data.get("external_attendance_id") or data.get("attendance_student_id") or "").strip()

        if not email and not phone:
            return {"error": "Either email or phone is required for enrollment.", "success": False}

        # Resolve or generate username
        username = (data.get("username") or "").strip()
        if not username:
            base_slug = slugify(f"{first_name}.{last_name}" if first_name else email.split("@")[0])
            base_slug = base_slug or "student"
            username = base_slug
            counter = 1
            while User.objects.filter(username=username).exclude(email__iexact=email).exists():
                username = f"{base_slug}{counter}"
                counter += 1

        # Look up existing user by email or username
        user = None
        if email:
            user = User.objects.filter(email__iexact=email).first()
        if not user and username:
            user = User.objects.filter(username=username).first()

        created = False
        if not user:
            temp_password = secrets.token_urlsafe(12)
            user = User.objects.create_user(
                username=username,
                email=email,
                password=temp_password,
                first_name=first_name,
                last_name=last_name,
            )
            created = True
        else:
            if first_name and not user.first_name:
                user.first_name = first_name
            if last_name and not user.last_name:
                user.last_name = last_name
            user.save(update_fields=["first_name", "last_name"])

        # Profile Resolution
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.role = "student"
        tenant = getattr(self.request, "tenant", None) or get_current_tenant()
        if tenant and not profile.tenant:
            profile.tenant = tenant
        if phone and not profile.phone:
            profile.phone = phone
        if external_id:
            profile.external_attendance_id = external_id
        if reg_code and not profile.external_attendance_id:
            profile.external_attendance_id = reg_code

        # Course Resolution
        course = None
        course_slug = (data.get("course_slug") or data.get("program") or "").strip()
        course_name = (data.get("course_name") or data.get("course") or "").strip()

        course_qs = Course.objects.all()
        if tenant:
            course_qs = course_qs.filter(models.Q(tenant=tenant) | models.Q(tenant__isnull=True))

        if course_slug:
            course = course_qs.filter(slug__iexact=course_slug).first()
        if not course and course_name:
            course = course_qs.filter(name__iexact=course_name).first()
            if not course:
                course = Course.objects.create(name=course_name, tenant=tenant, is_published=True)
        if not course:
            # Fallback to default or first active course
            course = course_qs.filter(is_published=True).first() or course_qs.first()

        if course:
            profile.course = course

        # Batch Resolution
        batch = None
        batch_name = (data.get("batch_name") or data.get("batch") or data.get("class_name") or "").strip()
        batch_qs = Batch.objects.all()
        if tenant:
            batch_qs = batch_qs.filter(models.Q(tenant=tenant) | models.Q(tenant__isnull=True))

        if batch_name:
            batch = batch_qs.filter(name__iexact=batch_name).first()
            if not batch and course:
                today = timezone.localdate()
                batch = Batch.objects.create(
                    name=batch_name,
                    tenant=tenant,
                    course=course,
                    mode="onsite",
                    batch_type="weekdays",
                    session_period="morning",
                    days_pattern="mon_wed_fri",
                    start_date=today,
                    end_date=today + timezone.timedelta(days=42),
                    is_published=True,
                )
        if not batch and course:
            batch = batch_qs.filter(course=course, is_published=True).first()

        if batch:
            profile.batch = batch

        profile.onboarding_stage = "welcome"
        profile.save()

        # Payment Processing (if provided)
        payment_info = data.get("payment") or {}
        payment_record = None
        if payment_info:
            amount_paid = Decimal(str(payment_info.get("amount_paid", "0.00")))
            amount_due = Decimal(str(payment_info.get("amount_due", str(course.fee if course else "0.00"))))
            pay_status = payment_info.get("status", "paid" if amount_paid >= amount_due and amount_due > 0 else "pending")

            payment_record = Payment.objects.create(
                student=user,
                course=course,
                batch=batch,
                amount_due=amount_due,
                amount_paid=amount_paid,
                status=pay_status,
            )
            if amount_paid > 0:
                Receipt.objects.create(
                    payment=payment_record,
                    amount=amount_paid,
                )
            payment_record.update_status()

        return {
            "success": True,
            "created": created,
            "user_id": user.id,
            "username": user.username,
            "email": user.email,
            "course_id": course.id if course else None,
            "course_name": course.name if course else None,
            "batch_id": batch.id if batch else None,
            "batch_name": batch.name if batch else None,
            "external_attendance_id": profile.external_attendance_id,
            "payment_id": payment_record.id if payment_record else None,
        }
