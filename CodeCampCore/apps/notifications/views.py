from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.accounts.decorators import role_required
from .models import NotificationLog
from django.http import HttpResponse
import csv
from django.utils import timezone
from .utils import send_and_log

@login_required
@role_required('hod')
def notification_center(request):
    qs = NotificationLog.objects.all()
    # simple filters via GET params
    ntype = request.GET.get('type')
    status = request.GET.get('status')
    q = request.GET.get('q')
    if ntype:
        qs = qs.filter(notification_type=ntype)
    if status:
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(subject__icontains=q) | qs.filter(body__icontains=q) | qs.filter(recipient__icontains=q)

    qs = qs.select_related('related_user','related_course','related_batch').order_by('-created_at')[:200]  # limit returns
    return render(request, 'notifications/notification_center.html', {'logs': qs})

@login_required
@role_required('hod')
def notification_detail(request, pk):
    log = get_object_or_404(NotificationLog, pk=pk)
    return render(request, 'notifications/notification_detail.html', {'log': log})

@login_required
@role_required('hod')
def resend_notification(request, pk):
    log = get_object_or_404(NotificationLog, pk=pk)
    # create a new log entry as a copy (safer) or update existing; below we reuse same entry but update fields
    new_log = NotificationLog.objects.create(
        notification_type=log.notification_type,
        subject=log.subject,
        body=log.body,
        recipient=log.recipient,
        related_user=log.related_user,
        related_course=log.related_course,
        related_batch=log.related_batch,
        status='queued'
    )
    success = send_and_log(new_log, html=True)
    return redirect('notification_detail', pk=new_log.pk)

@login_required
@role_required('hod')
def export_notifications_csv(request):
    qs = NotificationLog.objects.all().order_by('-created_at')[:1000]
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="notifications.csv"'
    writer = csv.writer(response)
    writer.writerow(['Type','Subject','Recipient','Status','Error','Created At','Sent At'])
    for l in qs:
        writer.writerow([l.notification_type, l.subject, l.recipient, l.status, l.error_message, l.created_at, l.sent_at])
    return response

@login_required
@role_required('hod')
def resend_failed_notifications(request):
    failed_logs = NotificationLog.objects.filter(status='failed')
    count = 0
    for log in failed_logs:
        from .utils import send_and_log
        success = send_and_log(log, html=True)
        if success:
            count += 1
    messages.success(request, f"{count} failed notifications re-sent successfully.")
    return redirect('notification_center')

from django.db.models import Count, Q

@login_required
@role_required('hod')
def notification_analytics(request):
    from .models import NotificationLog

    stats = NotificationLog.objects.values('notification_type').annotate(
        total=Count('id'),
        sent=Count('id', filter=Q(status='sent')),
        failed=Count('id', filter=Q(status='failed')),
    )

    totals = {
        'all': NotificationLog.objects.count(),
        'sent': NotificationLog.objects.filter(status='sent').count(),
        'failed': NotificationLog.objects.filter(status='failed').count(),
    }

    return render(request, 'notifications/analytics.html', {
        'stats': stats,
        'totals': totals,
    })
