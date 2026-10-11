from django.contrib import admin
from .models import Wallet, RechargeTransaction


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ['user', 'balance', 'updated_at']


@admin.register(RechargeTransaction)
class RechargeTransactionAdmin(admin.ModelAdmin):
    list_display = ['user', 'amount', 'reference', 'status', 'created_at']
    list_filter = ['status']
