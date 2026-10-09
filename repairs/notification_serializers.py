from django.urls import reverse
from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    reference_id = serializers.IntegerField(read_only=True)
    reference_status = serializers.CharField(source='reference.status', read_only=True, allow_null=True)
    url = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = (
            'id',
            'title',
            'message',
            'type',
            'is_read',
            'reference_id',
            'reference_status',
            'url',
            'created_at',
        )

    def get_url(self, notification):
        if notification.reference_id is None:
            return None
        return reverse('repair_detail', args=(notification.reference_id,))
