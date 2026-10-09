from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('account-management/', views.account_management, name='account_management'),
    path('account-management/activity/', views.account_activity, name='account_activity'),
    path('features/', views.features, name='features'),
    path('register/', views.register, name='register'),
    path('login/', views.LocalizedLoginView.as_view(template_name='accounts/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path(
        'password-reset/<uidb64>/<token>/',
        views.LocalizedPasswordResetConfirmView.as_view(
            template_name='accounts/password_reset_confirm.html',
            success_url=reverse_lazy('password_reset_complete'),
        ),
        name='password_reset_confirm',
    ),
    path(
        'password-reset/complete/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='accounts/password_reset_complete.html',
        ),
        name='password_reset_complete',
    ),
    path('account-settings/', views.account_settings, name='account_settings'),
    path('delete-account/', views.delete_account, name='delete_account'),
    path(
        'account-settings/users/<int:user_id>/send-password-reset/',
        views.send_account_password_reset,
        name='send_account_password_reset',
    ),
    path(
        'account-settings/users/<int:user_id>/role/',
        views.update_account_role,
        name='update_account_role',
    ),
    path(
        'account-management/users/<int:user_id>/status/',
        views.update_account_status,
        name='update_account_status',
    ),
    path('language/', views.language_switch, name='language_switch'),
]
