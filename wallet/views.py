from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db import transaction
from django.db.models import F
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import Wallet, RechargeTransaction
from .serializers import WalletSerializer, RechargeSerializer, RechargeCallbackSerializer


class WalletDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Get current wallet balance for the authenticated user",
        responses={200: WalletSerializer},
    )
    def get(self, request):
        wallet, _ = Wallet.objects.get_or_create(user=request.user)
        serializer = WalletSerializer(wallet)
        return Response(serializer.data)


class RechargeInitiateView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Initiate a wallet recharge. Creates a pending transaction.",
        request_body=RechargeSerializer,
        responses={201: RechargeSerializer},
    )
    def post(self, request):
        serializer = RechargeSerializer(data=request.data)
        if serializer.is_valid():
            if RechargeTransaction.objects.filter(
                reference=serializer.validated_data['reference']
            ).exists():
                return Response(
                    {'error': 'A transaction with this reference already exists.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            recharge = serializer.save(user=request.user)
            return Response(
                RechargeSerializer(recharge).data,
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RechargeCallbackView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_description=(
            "Process a mock recharge callback. Handles duplicate callbacks safely - "
            "the wallet is credited only once per transaction."
        ),
        request_body=RechargeCallbackSerializer,
        responses={
            200: 'Callback processed or already processed',
            404: 'Transaction not found',
        },
    )
    def post(self, request):
        serializer = RechargeCallbackSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        reference = serializer.validated_data['reference']
        callback_status = serializer.validated_data['status']

        try:
            txn = RechargeTransaction.objects.get(reference=reference)
        except RechargeTransaction.DoesNotExist:
            return Response(
                {'error': 'Transaction not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if txn.status in ('success', 'failed'):
            return Response({
                'message': 'Transaction already processed',
                'reference': txn.reference,
                'status': txn.status,
            })

        with transaction.atomic():
            txn = RechargeTransaction.objects.select_for_update().get(
                reference=reference
            )

            if txn.status != 'pending':
                return Response({
                    'message': 'Transaction already processed',
                    'reference': txn.reference,
                    'status': txn.status,
                })

            txn.status = callback_status
            txn.save()

            if callback_status == 'success':
                wallet, _ = Wallet.objects.select_for_update().get_or_create(
                    user=txn.user
                )
                wallet.balance = F('balance') + txn.amount
                wallet.save()
                wallet.refresh_from_db()

        return Response({
            'message': 'Callback processed successfully',
            'reference': txn.reference,
            'status': txn.status,
        })
