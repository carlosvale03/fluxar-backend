from django.urls import path
from .views import (
    RegisterView,
    CustomLoginView,
    CancelarExclusaoView,
    RenovarSessaoView,
    LogoutView,
    MeView,
    PlansView,
    ChangePasswordView,
    PedidoDeExclusaoView,
    VerifyEmailView,
    ResendVerificationView,
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
    AdminGlobalLogsView,
    AdminPlansView,
)

urlpatterns = [
    # Auth Public Endpoints
    path('auth/register/', RegisterView.as_view(), name='auth_register'),
    path('auth/login/', CustomLoginView.as_view(), name='auth_login'),
    path('auth/refresh/', RenovarSessaoView.as_view(), name='auth_refresh'),
    path('auth/logout/', LogoutView.as_view(), name='auth_logout'),
    path('auth/verify-email/', VerifyEmailView.as_view(), name='auth_verify_email'),
    path('auth/resend-verification/', ResendVerificationView.as_view(), name='auth_resend_verification'),
    path('auth/forgot-password/', ForgotPasswordView.as_view(), name='auth_forgot_password'),
    path('auth/reset-password/', ResetPasswordView.as_view(), name='auth_reset_password'),
    # Cancelamento da exclusão marcada, com o token do login (LGPD-08)
    path('auth/cancel-deletion/', CancelarExclusaoView.as_view(), name='auth_cancel_deletion'),

    # Auth Protected Endpoints
    path('auth/me/', MeView.as_view(), name='auth_me'),
    path('auth/me/avatar/', UserAvatarView.as_view(), name='auth_avatar'),

    # Página de planos (PERM-27)
    path('plans/', PlansView.as_view(), name='plans'),

    # User Management
    path('users/me/', MeView.as_view(), name='users_me'), # Alias comum em REST
    path('users/me/avatar/', UserAvatarView.as_view(), name='users_avatar'),
    path('users/me/password/', ChangePasswordView.as_view(), name='users_me_password'),
    # Pedido de exclusão da própria conta (LGPD-03 a LGPD-06)
    path('users/me/delete/', PedidoDeExclusaoView.as_view(), name='users_me_delete'),

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
    path('admin/plans/', AdminPlansView.as_view(), name='admin_plans'),
]
