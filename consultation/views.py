from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model
from django.utils import timezone
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import ConsultationSession
from .serializers import (
    SessionCreateSerializer,
    SessionDetailSerializer,
    SessionAssignSerializer,
    BillingRecordSerializer,
)
from .billing import perform_billing
from wallet.models import Wallet

User = get_user_model()


class SessionListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="List all sessions for the authenticated user",
        responses={200: SessionDetailSerializer(many=True)},
    )
    def get(self, request):
        if request.user.role == 'provider':
            sessions = ConsultationSession.objects.filter(provider=request.user)
        else:
            sessions = ConsultationSession.objects.filter(user=request.user)
        serializer = SessionDetailSerializer(sessions, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description=(
            "Create a new consultation session. "
            "Session starts in 'unassigned' state."
        ),
        request_body=SessionCreateSerializer,
        responses={201: SessionDetailSerializer},
    )
    def post(self, request):
        if request.user.role != 'user':
            return Response(
                {'error': 'Only users can create sessions'},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = SessionCreateSerializer(data=request.data)
        if serializer.is_valid():
            session = serializer.save(user=request.user)
            return Response(
                SessionDetailSerializer(session).data,
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SessionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Get session details by ID",
        responses={200: SessionDetailSerializer},
    )
    def get(self, request, pk):
        try:
            session = ConsultationSession.objects.get(pk=pk)
        except ConsultationSession.DoesNotExist:
            return Response(
                {'error': 'Session not found'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(SessionDetailSerializer(session).data)


class SessionAssignView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Assign a provider to the session (unassigned -> assigned)",
        request_body=SessionAssignSerializer,
        responses={
            200: SessionDetailSerializer,
            400: 'Invalid state transition or provider not found',
        },
    )
    def patch(self, request, pk):
        try:
            session = ConsultationSession.objects.get(pk=pk)
        except ConsultationSession.DoesNotExist:
            return Response(
                {'error': 'Session not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = SessionAssignSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        if not session.can_transition_to('assigned'):
            return Response(
                {'error': f"Cannot assign provider. Session is in '{session.status}' state."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        provider_id = serializer.validated_data['provider_id']
        provider = User.objects.get(id=provider_id)

        session.provider = provider
        session.transition_to('assigned')
        session.save()

        return Response(SessionDetailSerializer(session).data)


class SessionAcceptView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Provider accepts the assigned session (assigned -> accepted_by_provider)",
        responses={
            200: SessionDetailSerializer,
            400: 'Invalid state transition',
            403: 'Not the assigned provider',
        },
    )
    def patch(self, request, pk):
        try:
            session = ConsultationSession.objects.get(pk=pk)
        except ConsultationSession.DoesNotExist:
            return Response(
                {'error': 'Session not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if request.user.role != 'provider' or session.provider != request.user:
            return Response(
                {'error': 'Only the assigned provider can accept this session'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not session.can_transition_to('accepted_by_provider'):
            return Response(
                {'error': f"Cannot accept session. Current state is '{session.status}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        session.transition_to('accepted_by_provider')
        session.save()

        return Response(SessionDetailSerializer(session).data)


class SessionStartView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description=(
            "Start the consultation session (accepted_by_provider -> in_progress). "
            "Requires minimum balance of 5x per-minute cost."
        ),
        responses={
            200: SessionDetailSerializer,
            400: 'Invalid state transition or insufficient balance',
        },
    )
    def patch(self, request, pk):
        try:
            session = ConsultationSession.objects.get(pk=pk)
        except ConsultationSession.DoesNotExist:
            return Response(
                {'error': 'Session not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not session.can_transition_to('in_progress'):
            return Response(
                {'error': f"Cannot start session. Current state is '{session.status}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if request.user != session.user:
            return Response(
                {'error': 'Only the session owner can start the session'},
                status=status.HTTP_403_FORBIDDEN,
            )

        active_sessions = ConsultationSession.objects.filter(
            user=session.user,
            status='in_progress',
        ).exists()
        if active_sessions:
            return Response(
                {'error': 'You already have an active session in progress'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        wallet, _ = Wallet.objects.get_or_create(user=session.user)
        minimum_balance = session.per_minute_cost * 5
        if wallet.balance < minimum_balance:
            return Response(
                {
                    'error': 'Insufficient balance to start session',
                    'required_balance': str(minimum_balance),
                    'current_balance': str(wallet.balance),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        session.transition_to('in_progress')
        session.started_at = timezone.now()
        session.save()

        return Response(SessionDetailSerializer(session).data)


class SessionEndView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="End the session (in_progress -> completed). Bills for remaining time.",
        responses={
            200: SessionDetailSerializer,
            400: 'Invalid state transition',
        },
    )
    def patch(self, request, pk):
        try:
            session = ConsultationSession.objects.get(pk=pk)
        except ConsultationSession.DoesNotExist:
            return Response(
                {'error': 'Session not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not session.can_transition_to('completed'):
            return Response(
                {'error': f"Cannot end session. Current state is '{session.status}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if request.user == session.user:
            ended_by = 'user'
        elif request.user == session.provider:
            ended_by = 'provider'
        else:
            return Response(
                {'error': 'You are not part of this session'},
                status=status.HTTP_403_FORBIDDEN,
            )

        perform_billing(session)

        session.refresh_from_db()
        if session.status == 'completed':
            return Response(SessionDetailSerializer(session).data)

        session.transition_to('completed')
        session.ended_at = timezone.now()
        session.ended_by = ended_by
        session.end_reason = f'Ended by {ended_by}'
        session.save()

        return Response(SessionDetailSerializer(session).data)


class SessionBillingView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description=(
            "Trigger per-minute billing for an active session. "
            "Calculates elapsed time and charges for unbilled minutes. "
            "Automatically ends session if balance is insufficient."
        ),
        responses={
            200: 'Billing result with details',
            400: 'Session is not active',
        },
    )
    def post(self, request, pk):
        try:
            session = ConsultationSession.objects.get(pk=pk)
        except ConsultationSession.DoesNotExist:
            return Response(
                {'error': 'Session not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if session.status != 'in_progress':
            return Response(
                {'error': 'Billing can only be triggered for active sessions'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = perform_billing(session)

        session.refresh_from_db()

        return Response({
            'billing_result': {
                'new_minutes_billed': result['billed_minutes'],
                'amount_charged': str(result['total_billed']),
                'session_ended': result['session_ended'],
                'end_reason': result['reason'],
            },
            'session': SessionDetailSerializer(session).data,
        })


class SessionCancelView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Cancel a session (only before it starts)",
        responses={
            200: SessionDetailSerializer,
            400: 'Invalid state transition',
        },
    )
    def patch(self, request, pk):
        try:
            session = ConsultationSession.objects.get(pk=pk)
        except ConsultationSession.DoesNotExist:
            return Response(
                {'error': 'Session not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not session.can_transition_to('cancelled'):
            return Response(
                {'error': f"Cannot cancel session. Current state is '{session.status}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        session.transition_to('cancelled')
        session.ended_by = 'user' if request.user == session.user else 'provider'
        session.end_reason = 'Cancelled'
        session.save()

        return Response(SessionDetailSerializer(session).data)
