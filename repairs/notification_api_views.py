from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from .models import Notification
from .notification_serializers import NotificationSerializer


@api_view(('GET',))
@permission_classes((permissions.IsAuthenticated,))
def notification_list(request):
    notifications = Notification.objects.filter(user=request.user).select_related('reference')
    unread_count = notifications.filter(is_read=False).count()
    recent = notifications[:20]
    return Response({
        'unread_count': unread_count,
        'results': NotificationSerializer(recent, many=True).data,
    })


@api_view(('POST',))
@permission_classes((permissions.IsAuthenticated,))
def mark_notification_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    if not notification.is_read:
        notification.is_read = True
        notification.save(update_fields=('is_read',))
    return Response(NotificationSerializer(notification).data)


@api_view(('POST',))
@permission_classes((permissions.IsAuthenticated,))
def mark_all_notifications_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return Response(status=status.HTTP_204_NO_CONTENT)
