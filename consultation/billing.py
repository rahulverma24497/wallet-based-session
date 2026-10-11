from decimal import Decimal
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from wallet.models import Wallet
from .models import BillingRecord


def perform_billing(session):
    if session.status != 'in_progress':
        return {
            'billed_minutes': 0,
            'total_billed': Decimal('0.00'),
            'session_ended': False,
            'reason': None,
        }

    now = timezone.now()
    elapsed_seconds = (now - session.started_at).total_seconds()
    total_elapsed_minutes = int(elapsed_seconds // 60)

    new_billed = 0
    new_amount = Decimal('0.00')

    with transaction.atomic():
        wallet = Wallet.objects.select_for_update().get(user=session.user)

        for minute_num in range(session.billed_minutes + 1, total_elapsed_minutes + 1):
            already_billed = BillingRecord.objects.filter(
                session=session,
                minute_number=minute_num,
            ).exists()
            if already_billed:
                continue

            if wallet.balance < session.per_minute_cost:
                session.status = 'completed'
                session.ended_at = now
                session.ended_by = 'system'
                session.end_reason = 'Insufficient Balance'
                session.save()
                return {
                    'billed_minutes': new_billed,
                    'total_billed': new_amount,
                    'session_ended': True,
                    'reason': 'Insufficient Balance',
                }

            wallet.balance -= session.per_minute_cost
            wallet.save()

            BillingRecord.objects.create(
                session=session,
                minute_number=minute_num,
                amount=session.per_minute_cost,
            )

            session.billed_minutes = minute_num
            session.total_billed_amount += session.per_minute_cost
            session.save()

            new_billed += 1
            new_amount += session.per_minute_cost

        wallet.refresh_from_db()
        if wallet.balance < session.per_minute_cost:
            session.status = 'completed'
            session.ended_at = now
            session.ended_by = 'system'
            session.end_reason = 'Insufficient Balance'
            session.save()
            return {
                'billed_minutes': new_billed,
                'total_billed': new_amount,
                'session_ended': True,
                'reason': 'Insufficient Balance',
            }

    return {
        'billed_minutes': new_billed,
        'total_billed': new_amount,
        'session_ended': False,
        'reason': None,
    }
