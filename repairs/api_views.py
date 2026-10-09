from rest_framework import permissions, serializers, viewsets
from .models import RepairRequest
from .notifications import notify_new_repair, notify_status_change
from .serializers import RepairRequestSerializer


class IsOwnerOrSupervisor(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return request.user.is_supervisor or obj.reported_by == request.user


class RepairRequestViewSet(viewsets.ModelViewSet):
    serializer_class = RepairRequestSerializer
    permission_classes = (permissions.IsAuthenticated, IsOwnerOrSupervisor)

    def get_queryset(self):
        queryset = RepairRequest.objects.select_related('reported_by')
        return queryset if self.request.user.is_supervisor else queryset.filter(reported_by=self.request.user)

    def perform_create(self, serializer):
        user = self.request.user
        if not user.is_supervisor:
            if not user.room_number:
                raise serializers.ValidationError({
                    'location': 'Your account has no room number. Please contact a supervisor before submitting.',
                })
            repair = serializer.save(reported_by=user, location=user.room_number)
        else:
            repair = serializer.save(reported_by=user)
        notify_new_repair(repair)

    def perform_update(self, serializer):
        previous_status = serializer.instance.status
        repair = serializer.save()
        if repair.status != previous_status:
            notify_status_change(repair, previous_status)
