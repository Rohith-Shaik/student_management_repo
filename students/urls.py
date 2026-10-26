
from django.urls import path
from . import views
#from .views import StudentPasswordResetView, AdminPasswordResetView
from students.views import StudentPasswordResetView, AdminPasswordResetView
app_name = 'students'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('accounts/register/', views.register, name='register'),

    path('student-dashboard/',views.student_dashboard,name='student_dashboard'),

    path('student-profile/complete/',views.complete_student_profile,name='complete_student_profile'),

    path('attendance/mark/', views.mark_attendance,name='mark_attendance'),

    path('attendance/history/',views.attendance_list,name='attendance_list'),
    path('my-attendance/',views.student_attendance,name='student_attendance'),
    path('students/', views.student_list, name='student_list'),
    path('students/add/', views.student_create, name='student_create'),
    path('students/edit/<int:pk>/', views.student_update, name='student_update'),
    path('students/delete/<int:pk>/', views.student_delete, name='student_delete'),

    path('courses/', views.course_list, name='course_list'),
    path('courses/add/', views.course_create, name='course_create'),
    path('courses/edit/<int:pk>/', views.course_update, name='course_update'),
    path('courses/delete/<int:pk>/', views.course_delete, name='course_delete'),

    path('subjects/add/',views.subject_create,name='subject_create'),
    path('exams/add/',views.exam_create,name='exam_create'),

    path('results/enter/',views.enter_marks,name='enter_marks'),

    path('results/',views.results_list,name='results_list'),

    path('my-results/', views.my_results, name='my_results'),

    path('results/edit/<int:pk>',views.edit_mark,name='edit_mark'),
    path('results/delete/<int:pk>',views.delete_mark,name='delete_mark'),

    path('report-card/<int:student_id>/',views.report_card,name='report_card'),
    path('statistics/',views.statistics_dashboard,name='statistics_dashboard'),

    # Fee Management
    path('fees/', views.fee_list, name='fee_list'),
    path('fees/assign/', views.assign_fee, name='assign_fee'),
    path(
        'fees/<int:fee_id>/payment/',
        views.record_fee_payment,
        name='record_fee_payment'
    ),
    path(
        'fees/payment-history/',
        views.fee_payment_history,
        name='fee_payment_history'
    ),
    path('fees/payment/<int:payment_id>/receipt',views.fee_receipt, name='fee_receipt'),

    path(
        'my-fees/',
        views.student_fee_balances,
        name='student_fee_balances'
    ),
    path(
        'my-fee-payments/',
        views.student_fee_payment_history,
        name='student_fee_payment_history'
    ),
    path(
        'fees/<int:fee_id>/edit/',
        views.edit_fee,
        name='edit_fee'
    ),
    path(
        'fees/<int:fee_id>/delete/',
        views.delete_fee,
        name='delete_fee'
    ),
    path(
        'fees/recycle-bin/',
        views.fee_recycle_bin,
        name='fee_recycle_bin'
    ),
    path(
        'fees/<int:fee_id>/restore/',
        views.restore_fee,
        name='restore_fee'
    ),

    path(
        'attendance/report/',
        views.attendance_report,
        name='attendance_report'
    ),

    path(
        'attendance/export/',
        views.export_attendance_report,
        name='export_attendance_report'
    ),
    path(
        'attendance/student/<int:student_id>/',
        views.individual_attendance_report,
        name='individual_attendance_report'
    ),
    path(
        'my-attendance-report/',
        views.my_attendance_report,
        name='my_attendance_report'
    ),

    path(
        'attendance/low-attendance/',
        views.low_attendance_students,
        name='low_attendance_students'
    ),

    path(
        'attendance/student/<int:student_id>/pdf/',
        views.individual_attendance_report_pdf,
        name='individual_attendance_report_pdf',
    ),
    path(
        'admin-register/',
        views.admin_register,
        name='admin_register',
    ),
    path(
        'admin-requests/',
        views.admin_registration_requests,
        name='admin_registration_requests',
    ),
    path(
        'admin-requests/<int:request_id>/approve/',
        views.approve_admin_request,
        name='approve_admin_request',
    ),
    path(
        'admin-requests/<int:request_id>/reject/',
        views.reject_admin_request,
        name='reject_admin_request',
    ),

    path(
        'attendance/send-alerts/',
        views.send_low_attendance_alerts,
        name='send_low_attendance_alerts'
    ),
    path(
        'student/forgot-password/',
        StudentPasswordResetView.as_view(),
        name='student_password_reset',
    ),
    path(
        'admin/forgot-password/',
        AdminPasswordResetView.as_view(),
        name='admin_password_reset',
    ),


    path(
        'students/reactivate/<int:pk>/',
        views.student_reactivate,
        name='student_reactivate',
    ),
    path(
        'students/permanent-delete/<int:pk>/',
        views.student_permanent_delete,
        name='student_permanent_delete',
    ),

]

