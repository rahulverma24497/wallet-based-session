from django.contrib import admin
from .models import ConsultationSession, BillingRecord


@admin.register(ConsultationSession)
class ConsultationSessionAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'user', 'provider', 'status', 'per_minute_cost',
        'billed_minutes', 'total_billed_amount', 'created_at',
    ]
    list_filter = ['status']


@admin.register(BillingRecord)
class BillingRecordAdmin(admin.ModelAdmin):
    list_display = ['session', 'minute_number', 'amount', 'billed_at']
