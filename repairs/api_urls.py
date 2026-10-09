from django.urls import path
from rest_framework.routers import DefaultRouter
from .api_views import RepairRequestViewSet
from . import notification_api_views

router = DefaultRouter()
router.register('repairs', RepairRequestViewSet, basename='api-repair')
urlpatterns = [
    *router.urls,
    path('notifications/', notification_api_views.notification_list, name='api-notifications'),
    path('notifications/<int:pk>/read/', notification_api_views.mark_notification_read, name='api-notification-read'),
    path('notifications/read-all/', notification_api_views.mark_all_notifications_read, name='api-notifications-read-all'),
]
