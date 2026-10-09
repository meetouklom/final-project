from .models import Notification
from accounts.models import User


def notify_new_repair(repair):
    supervisors = User.objects.filter(role=User.Role.SUPERVISOR, is_active=True)
    Notification.objects.bulk_create([
        Notification(
            user=supervisor,
            title='มีรายการแจ้งซ่อมใหม่',
            message=f'{repair.reported_by.get_full_name() or repair.reported_by.username}: {repair.title}',
            type=Notification.Type.NEW_REPAIR,
            reference=repair,
        )
        for supervisor in supervisors
    ])


def notify_status_change(repair, previous_status):
    Notification.objects.create(
        user=repair.reported_by,
        title='อัปเดตสถานะงานซ่อม',
        message=f'{repair.title}: {dict(repair.Status.choices)[previous_status]} → {repair.get_status_display()}',
        type=Notification.Type.STATUS_CHANGE,
        reference=repair,
    )


def notify_new_comment(repair, author, body):
    if author.is_supervisor:
        recipients = User.objects.filter(pk=repair.reported_by_id)
    else:
        recipients = User.objects.filter(role=User.Role.SUPERVISOR, is_active=True)
    recipients = recipients.exclude(pk=author.pk)
    Notification.objects.bulk_create([
        Notification(
            user=recipient,
            title='มีความคิดเห็นใหม่',
            message=f'{repair.title}: {body[:350]}',
            type=Notification.Type.COMMENT,
            reference=repair,
        )
        for recipient in recipients
    ])
