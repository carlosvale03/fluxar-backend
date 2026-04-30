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
    UserAvatarView,
    AdminUserListView,
    AdminUserDetailView,
    AdminStatsView,
    AdminUserFinancialStatsView,
    AdminUserLogsView,
    AdminResetPasswordView,
    AdminHardDeleteView,
    AdminClearUserDataView,
    AdminSystemSettingsView,
    AdminGlobalLogsView
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
    path('users/me/avatar/', UserAvatarView.as_view(), name='users_avatar'),
    path('users/me/password/', ChangePasswordView.as_view(), name='users_me_password'),

    # System
    path('health/', health_check, name='health_check'),
    
    # Admin Backoffice
    path('admin/users/', AdminUserListView.as_view(), name='admin_users_list'),
    path('admin/users/<uuid:pk>/', AdminUserDetailView.as_view(), name='admin_users_detail'),
    path('admin/users/<uuid:pk>/hard-delete/', AdminHardDeleteView.as_view(), name='admin_user_hard_delete'),
    path('admin/users/<uuid:pk>/clear-data/', AdminClearUserDataView.as_view(), name='admin_user_clear_data'),
    path('admin/users/<uuid:pk>/financial-stats/', AdminUserFinancialStatsView.as_view(), name='admin_user_financial_stats'),
    path('admin/users/<uuid:pk>/logs/', AdminUserLogsView.as_view(), name='admin_user_logs'),
    path('admin/users/<uuid:pk>/reset-password/', AdminResetPasswordView.as_view(), name='admin_user_reset_password'),
    path('admin/stats/', AdminStatsView.as_view(), name='admin_stats'),
    path('admin/settings/', AdminSystemSettingsView.as_view(), name='admin_settings'),
    path('admin/logs/', AdminGlobalLogsView.as_view(), name='admin-logs'),

    # JWT (Standard + Custom Claims)
    path('token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
]
