from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        STUDENT = 'student', 'Student'
        SUPERVISOR = 'supervisor', 'Dormitory Supervisor'

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT)
    room_number = models.CharField(max_length=20, blank=True)

    @property
    def is_supervisor(self):
        return self.role == self.Role.SUPERVISOR


class AccountAuditLog(models.Model):
    class Action(models.TextChoices):
        ROLE_CHANGED = 'role_changed', 'Role changed'
        ACCOUNT_DEACTIVATED = 'account_deactivated', 'Account deactivated'
        ACCOUNT_ACTIVATED = 'account_activated', 'Account activated'

    actor = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='account_actions_performed',
    )
    actor_username = models.CharField(max_length=150)
    target = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='account_actions_received',
    )
    target_username = models.CharField(max_length=150)
    action = models.CharField(max_length=32, choices=Action.choices)
    old_value = models.CharField(max_length=20)
    new_value = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at', '-pk')
        verbose_name = 'account audit log'
        verbose_name_plural = 'account audit logs'

    def __str__(self):
        return f'{self.actor_username} changed {self.target_username}: {self.action}'
