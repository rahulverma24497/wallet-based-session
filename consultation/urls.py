from django.urls import path
from . import views

urlpatterns = [
    path('', views.SessionListCreateView.as_view(), name='session-list-create'),
    path('<int:pk>/', views.SessionDetailView.as_view(), name='session-detail'),
    path('<int:pk>/assign/', views.SessionAssignView.as_view(), name='session-assign'),
    path('<int:pk>/accept/', views.SessionAcceptView.as_view(), name='session-accept'),
    path('<int:pk>/start/', views.SessionStartView.as_view(), name='session-start'),
    path('<int:pk>/end/', views.SessionEndView.as_view(), name='session-end'),
    path('<int:pk>/cancel/', views.SessionCancelView.as_view(), name='session-cancel'),
    path('<int:pk>/billing/', views.SessionBillingView.as_view(), name='session-billing'),
]
