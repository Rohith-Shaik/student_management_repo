
from django.contrib import admin
from .models import Student,Course,FeeRecord,FeePayment


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = (
        'student_id',
        'first_name',
        'last_name',
        'email',
        'course',
        'user',
    )

    search_fields = (
        'student_id',
        'first_name',
        'last_name',
        'email',
    )
    fields = (
        'student_id',
        'first_name',
        'last_name',
        'email',
        'phone',
        'gender',
        'course',
        'course_ref',
        'date_of_birth',
        'address',
        'user',
    )

    list_filter = ('gender', 'course')

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('course_code', 'course_name', 'created_at')
    search_fields = ('course_code', 'course_name')



class FeePaymentInline(admin.TabularInline):
    model = FeePayment
    extra = 0


@admin.register(FeeRecord)
class FeeRecordAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'student',
        'fee_type',
        'academic_year',
        'total_amount',
        'due_date',
    )
    search_fields = ('student__id', 'fee_type', 'academic_year')
    list_filter = ('fee_type', 'academic_year')
    inlines = [FeePaymentInline]


@admin.register(FeePayment)
class FeePaymentAdmin(admin.ModelAdmin):
    list_display = (
        'receipt_number',
        'fee_record',
        'amount',
        'payment_date',
        'payment_method',
    )
    search_fields = ('receipt_number',)
    list_filter = ('payment_method', 'payment_date')
