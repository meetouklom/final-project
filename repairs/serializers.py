from rest_framework import serializers
from .models import RepairRequest


class RepairRequestSerializer(serializers.ModelSerializer):
    reported_by_name = serializers.CharField(source='reported_by.get_full_name', read_only=True)

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get('request')
        if request is not None and not request.user.is_supervisor:
            fields['location'].read_only = True
        return fields

    class Meta:
        model = RepairRequest
        fields = ('id', 'title', 'description', 'category', 'location', 'status', 'reported_by_name', 'created_at', 'updated_at')
        read_only_fields = ('reported_by_name',)

    def validate_status(self, value):
        request = self.context.get('request')
        if request is not None and not request.user.is_supervisor:
            raise serializers.ValidationError('Only supervisors can change repair status.')
        return value
