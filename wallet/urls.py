from django.urls import path
from . import views

urlpatterns = [
    path('', views.WalletDetailView.as_view(), name='wallet-detail'),
    path('recharge/', views.RechargeInitiateView.as_view(), name='recharge-initiate'),
    path('recharge/callback/', views.RechargeCallbackView.as_view(), name='recharge-callback'),
]
