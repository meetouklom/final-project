from django.conf import settings
from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator


class RepairRequest(models.Model):
    class Category(models.TextChoices):
        ELECTRICITY = 'electricity', 'Electricity'
        PLUMBING = 'plumbing', 'Plumbing'
        FURNITURE = 'furniture', 'Furniture'
        INTERNET = 'internet', 'Internet'
        OTHER = 'other', 'Other'

    class Status(models.TextChoices):
        RECEIVED = 'received', 'Received'
        IN_PROGRESS = 'in_progress', 'In progress'
        WAITING = 'waiting', 'Waiting for parts'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'

    class AIUrgency(models.TextChoices):
        URGENT = 'urgent', 'Urgent'
        NORMAL = 'normal', 'Normal'
        LOW = 'low', 'Low'

    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='repair_requests')
    title = models.CharField(max_length=160)
    description = models.TextField()
    category = models.CharField(max_length=30, choices=Category.choices)
    location = models.CharField(max_length=120)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RECEIVED)
    rating = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=(MinValueValidator(1), MaxValueValidator(5)),
    )
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='assigned_repairs')
    image = models.ImageField(upload_to='repair_images/', blank=True, null=True)
    supervisor_note = models.TextField(blank=True)
    ai_summary = models.TextField(blank=True, default='', db_default='')
    ai_summary_th = models.TextField(blank=True, default='', db_default='')
    ai_summary_en = models.TextField(blank=True, default='', db_default='')
    ai_suggested_category = models.CharField(
        max_length=30,
        choices=Category.choices,
        blank=True,
        default='',
        db_default='',
    )
    ai_urgency = models.CharField(
        max_length=20,
        choices=AIUrgency.choices,
        blank=True,
        default='',
        db_default='',
    )
    ai_reason = models.TextField(blank=True, default='', db_default='')
    ai_reason_th = models.TextField(blank=True, default='', db_default='')
    ai_reason_en = models.TextField(blank=True, default='', db_default='')
    ai_analyzed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f'#{self.pk} {self.title}'


class RepairComment(models.Model):
    repair = models.ForeignKey(RepairRequest, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='repair_comments')
    body = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('created_at', 'pk')

    def __str__(self):
        return f'Comment on repair #{self.repair_id} by {self.author}'


class Notification(models.Model):
    class Type(models.TextChoices):
        NEW_REPAIR = 'new_repair', 'New repair request'
        STATUS_CHANGE = 'status_change', 'Repair status changed'
        COMMENT = 'comment', 'New repair comment'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=160)
    message = models.CharField(max_length=500)
    type = models.CharField(max_length=20, choices=Type.choices)
    is_read = models.BooleanField(default=False)
    reference = models.ForeignKey(
        RepairRequest,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at', '-pk')

    def __str__(self):
        return f'{self.title} for {self.user}'
