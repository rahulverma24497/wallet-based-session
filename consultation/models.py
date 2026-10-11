from django.db import models
from django.conf import settings
from django.utils import timezone


class ConsultationSession(models.Model):
    STATUS_CHOICES = (
        ('unassigned', 'Unassigned'),
        ('assigned', 'Assigned'),
        ('accepted_by_provider', 'Accepted by Provider'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )

    ENDED_BY_CHOICES = (
        ('user', 'User'),
        ('provider', 'Provider'),
        ('system', 'System'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sessions_as_user',
    )
    provider = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sessions_as_provider',
    )
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default='unassigned')
    per_minute_cost = models.DecimalField(max_digits=10, decimal_places=2, default=50.00)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    ended_by = models.CharField(max_length=10, choices=ENDED_BY_CHOICES, null=True, blank=True)
    end_reason = models.CharField(max_length=255, null=True, blank=True)
    billed_minutes = models.IntegerField(default=0)
    total_billed_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    VALID_TRANSITIONS = {
        'unassigned': ['assigned', 'cancelled'],
        'assigned': ['accepted_by_provider', 'cancelled'],
        'accepted_by_provider': ['in_progress', 'cancelled'],
        'in_progress': ['completed'],
    }

    def can_transition_to(self, new_status):
        """Check if the transition is valid."""
        allowed = self.VALID_TRANSITIONS.get(self.status, [])
        return new_status in allowed

    def transition_to(self, new_status):
        """Attempt a state transition. Raises ValueError if invalid."""
        if not self.can_transition_to(new_status):
            raise ValueError(
                f"Invalid transition from '{self.status}' to '{new_status}'"
            )
        self.status = new_status

    @property
    def duration_minutes(self):
        """Calculate how many full minutes the session has been running."""
        if not self.started_at:
            return 0
        end_time = self.ended_at or timezone.now()
        delta = (end_time - self.started_at).total_seconds()
        return int(delta // 60)

    def __str__(self):
        return f"Session #{self.id} ({self.status})"

    class Meta:
        ordering = ['-created_at']


class BillingRecord(models.Model):
    """
    Tracks each individual billed minute.
    The unique_together constraint prevents double-billing for the same minute.
    """
    session = models.ForeignKey(
        ConsultationSession,
        on_delete=models.CASCADE,
        related_name='billing_records',
    )
    minute_number = models.IntegerField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    billed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('session', 'minute_number')

    def __str__(self):
        return f"Session#{self.session_id} Minute#{self.minute_number} - {self.amount}"
