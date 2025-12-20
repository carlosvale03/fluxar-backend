from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .serializers_auth import CustomTokenObtainPairView
from .views import (
    RegisterView,
    CustomLoginView,
    MeView,
    ChangePasswordView,
    VerifyEmailView,
    ForgotPasswordView,
    ResetPasswordView,
    health_check,
    UserAvatarView
)

urlpatterns = [
    # Auth Public Endpoints
    path('auth/register/', RegisterView.as_view(), name='auth_register'),
    path('auth/login/', CustomLoginView.as_view(), name='auth_login'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='auth_refresh'),
    path('auth/verify-email/', VerifyEmailView.as_view(), name='auth_verify_email'),
    path('auth/forgot-password/', ForgotPasswordView.as_view(), name='auth_forgot_password'),
    path('auth/reset-password/', ResetPasswordView.as_view(), name='auth_reset_password'),

    # Auth Protected Endpoints
    path('auth/me/', MeView.as_view(), name='auth_me'),
    path('auth/me/avatar/', UserAvatarView.as_view(), name='auth_avatar'),

    # User Management
    path('users/me/', MeView.as_view(), name='users_me'), # Alias comum em REST
    path('users/me/password/', ChangePasswordView.as_view(), name='users_me_password'),

    # System
    path('health/', health_check, name='health_check'),
    
    # JWT (Standard + Custom Claims)
    path('token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
]
