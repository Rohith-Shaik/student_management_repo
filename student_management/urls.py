
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.contrib.auth import views as auth_views

from students import views as student_views

urlpatterns = [
    path('admin/', admin.site.urls),

    # Separate login pages
    path('admin-login/', student_views.admin_login, name='admin_login'),
    path('student-login/', student_views.student_login, name='student_login'),

    # Keep the existing login URL working
    path(
        'accounts/login/',
        RedirectView.as_view(url='/student-login/', permanent=False),
        name='login',
    ),

    # Keep the existing logout URL
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),

    # Default home page
    path(
        '',
        RedirectView.as_view(
            pattern_name='students:dashboard',
            permanent=False,
        ),
    ),

    # Student password reset — use the custom form
    path(
        'accounts/password-reset/',
        student_views.StudentPasswordResetView.as_view(),
        name='password_reset',
    ),

    # Confirmation after requesting a reset
    path(
        'accounts/password-reset/done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='registration/password_reset_done.html',
        ),
        name='password_reset_done',
    ),

    # Link opened from the email
    path(
        'accounts/reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='registration/password_reset_confirm.html',
            success_url='/accounts/reset/done/',
        ),
        name='password_reset_confirm',
    ),

    # Confirmation after changing the password
    path(
        'accounts/reset/done/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='registration/password_reset_complete.html',
        ),
        name='password_reset_complete',
    ),

    # Include existing student/course URLs only once
    path('', include('students.urls')),
]
