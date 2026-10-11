from rest_framework import serializers
from .models import Wallet, RechargeTransaction


class WalletSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Wallet
        fields = ['id', 'username', 'balance', 'created_at', 'updated_at']
        read_only_fields = ['balance']


class RechargeSerializer(serializers.ModelSerializer):
    class Meta:
        model = RechargeTransaction
        fields = ['id', 'amount', 'reference', 'status', 'created_at']
        read_only_fields = ['status', 'created_at']

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        return value


class RechargeCallbackSerializer(serializers.Serializer):
    reference = serializers.CharField()
    status = serializers.ChoiceField(choices=['success', 'failed'])
