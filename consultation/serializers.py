from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import ConsultationSession, BillingRecord

User = get_user_model()


class SessionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConsultationSession
        fields = ['id', 'per_minute_cost']

    def validate_per_minute_cost(self, value):
        if value <= 0:
            raise serializers.ValidationError("Per-minute cost must be positive.")
        return value


class SessionDetailSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()
    provider = serializers.StringRelatedField()
    duration_minutes = serializers.IntegerField(read_only=True)

    class Meta:
        model = ConsultationSession
        fields = [
            'id', 'user', 'provider', 'status', 'per_minute_cost',
            'started_at', 'ended_at', 'ended_by', 'end_reason',
            'billed_minutes', 'total_billed_amount', 'duration_minutes',
            'created_at', 'updated_at',
        ]


class SessionAssignSerializer(serializers.Serializer):
    provider_id = serializers.IntegerField()

    def validate_provider_id(self, value):
        try:
            provider = User.objects.get(id=value, role='provider')
        except User.DoesNotExist:
            raise serializers.ValidationError("Provider not found or user is not a provider.")
        return value


class BillingRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillingRecord
        fields = ['id', 'minute_number', 'amount', 'billed_at']
