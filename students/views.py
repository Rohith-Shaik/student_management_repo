
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.contrib import messages
from django.db.models import Q,Count,Sum,F,DecimalField
from decimal import Decimal
from .models import Student,AdminRegistrationRequest
from .forms import StudentForm,ExamForm,SubjectForm
from django.db.models.functions import Coalesce
from .models import Course,Attendance,Subject,Mark,Exam,FeePayment,FeeRecord,LowAttendanceAlert
from .course_forms import CourseForm
from django.contrib.auth.decorators import login_required,user_passes_test
from .forms import UserRegistrationForm,FeeRecordForm,FeePaymentForm,AdminRegisterForm
from django.contrib.admin.views.decorators import staff_member_required
from functools import wraps
from django.contrib.auth import authenticate, login
from django.utils.http import url_has_allowed_host_and_scheme
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.crypto import get_random_string
from datetime import date as python_date
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST
from django.db.models import Avg
import csv
from django.http import HttpResponse
from io import BytesIO
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from django.conf import settings
from django.core.mail import send_mail
from django.contrib.auth import views as auth_views
from django.urls import reverse_lazy
from .forms import StudentPasswordResetForm, AdminPasswordResetForm
from django.contrib.auth import logout
from .forms import StudentProfileForm
from django.db.models.deletion import ProtectedError, RestrictedError
@login_required
def student_list(request):
    query = request.GET.get('q', '').strip()

    students = Student.objects.all()

    if query:
        students = students.filter(
            Q(student_id__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(email__icontains=query)
            | Q(course__icontains=query)
        )

    paginator = Paginator(students, 5)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'query': query,
        'total_students': Student.objects.count(),
    }

    return render(
        request,
        'students/student_list.html',
        context
    )


@staff_member_required
def student_create(request):
    if request.method == 'POST':
        form = StudentForm(request.POST)

        if form.is_valid():
            User = get_user_model()

            with transaction.atomic():
                student = form.save(commit=False)

                # Create the student record first.
                student.save()
                form.save_m2m()

                # Generate a unique login username.
                base_username = f"student{student.student_id}"
                username = base_username
                number = 1

                while User.objects.filter(
                    username=username
                ).exists():
                    username = f"{base_username}_{number}"
                    number += 1

                # Generate a random initial password.
                temporary_password = get_random_string(16)

                # Create a normal student account.
                user = User.objects.create_user(
                    username=username,
                    email=student.email,
                    password=temporary_password,
                    first_name=student.first_name,
                    last_name=student.last_name,
                    is_staff=False,
                    is_superuser=False,
                )

                # Link the account to the student record.
                student.user = user
                student.save(update_fields=['user'])

            # Show the credentials to the admin once.
            messages.success(
                request,
                f"Student created successfully. "
                f"Login username: {username}. "
                f"Temporary password: {temporary_password}. "
                f"Share these credentials securely."
            )

            return redirect('students:student_list')

    else:
        form = StudentForm()

    return render(
        request,
        'students/student_form.html',
        {'form': form}
    )

@staff_member_required
def student_update(request, pk):
    student = get_object_or_404(Student, pk=pk)

    if request.method == 'POST':
        form = StudentForm(request.POST, instance=student)

        if form.is_valid():
            form.save()
            messages.success(
                request,
                'Student updated successfully!'
            )
            return redirect('students:student_list')
    else:
        form = StudentForm(instance=student)

    return render(
        request,
        'students/student_form.html',
        {'form': form, 'title': 'Update Student'}
    )



@staff_member_required
def student_delete(request, pk):
    student = get_object_or_404(Student, pk=pk)

    if request.method == 'POST':
        if student.is_active:
            student.is_active = False
            student.save(update_fields=['is_active'])

            messages.success(
                request,
                'Student deactivated successfully. '
                'All fee and attendance records have been preserved.'
            )
        else:
            messages.info(
                request,
                'This student is already inactive.'
            )

        return redirect('students:student_list')

    return render(
        request,
        'students/student_confirm_delete.html',
        {'student': student}
    )

@staff_member_required
def student_permanent_delete(request, pk):
    student = get_object_or_404(Student, pk=pk)

    # Permanent deletion requires an explicit POST request.
    if request.method == 'POST':
        # Preserve fee, attendance, and other related history.
        # Check reverse foreign-key and one-to-one relationships.
        has_related_records = False

        for relation in Student._meta.related_objects:
            if relation.one_to_many or relation.one_to_one:
                related_model = relation.related_model
                related_field = relation.field.name

                if related_model._base_manager.filter(
                    **{related_field: student}
                ).exists():
                    has_related_records = True
                    break

        if has_related_records:
            messages.error(
                request,
                'Permanent deletion is not allowed because this '
                'student has related records. Deactivate the student '
                'to preserve fee records and attendance history.'
            )
            return redirect('students:student_list')

        try:
            with transaction.atomic():
                student.delete()

            messages.success(
                request,
                'Student permanently deleted successfully.'
            )

        except (ProtectedError, RestrictedError):
            messages.error(
                request,
                'This student cannot be permanently deleted because '
                'protected records depend on this student. '
                'The student record has been preserved.'
            )

        return redirect('students:student_list')

    return render(
        request,
        'students/student_permanent_delete.html',
        {'student': student},
    )

@staff_member_required
def student_reactivate(request, pk):
    student = get_object_or_404(Student, pk=pk)

    if request.method == 'POST':
        if not student.is_active:
            student.is_active = True
            student.save(update_fields=['is_active'])

            messages.success(
                request,
                'Student reactivated successfully!'
            )
        else:
            messages.info(
                request,
                'This student is already active.'
            )

    return redirect('students:student_list')


@login_required

def dashboard(request):
    total_students = Student.objects.count()
    total_courses = Course.objects.count()

    courses = Course.objects.annotate(
        student_count=Count('students')
    ).order_by('course_name')

    recent_students = Student.objects.order_by(
        '-created_at'
    )[:5]

    context = {
        'total_students': total_students,
        'total_courses': total_courses,
        'courses': courses,
        'recent_students': recent_students,
    }

    return render(request, 'students/dashboard.html', context)


@login_required
def course_list(request):
    courses = Course.objects.all()

    return render(
        request,
        'students/course_list.html',
        {'courses': courses}
    )

@staff_member_required
def course_create(request):
    if request.method == 'POST':
        form = CourseForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(
                request,
                'Course added successfully!'
            )
            return redirect('students:course_list')
    else:
        form = CourseForm()

    return render(
        request,
        'students/course_form.html',
        {'form': form, 'title': 'Add Course'}
    )

@staff_member_required
def course_update(request, pk):
    course = get_object_or_404(Course, pk=pk)

    if request.method == 'POST':
        form = CourseForm(request.POST, instance=course)

        if form.is_valid():
            form.save()
            messages.success(
                request,
                'Course updated successfully!'
            )
            return redirect('students:course_list')
    else:
        form = CourseForm(instance=course)

    return render(
        request,
        'students/course_form.html',
        {'form': form, 'title': 'Edit Course'}
    )

@staff_member_required
def course_delete(request, pk):
    course = get_object_or_404(Course, pk=pk)

    if request.method == 'POST':
        course.delete()
        messages.success(
            request,
            'Course deleted successfully!'
        )
        return redirect('students:course_list')

    return render(
        request,
        'students/course_confirm_delete.html',
        {'course': course}
    )




def register(request):
    if request.user.is_authenticated:
        if request.user.is_staff:
            return redirect('students:dashboard')

        if Student.objects.filter(user=request.user).exists():
            return redirect('students:student_dashboard')

        return redirect('students:complete_student_profile')

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)

        if form.is_valid():
            user = form.save(commit=False)
            user.is_staff = False
            user.is_superuser = False
            user.save()

            login(request, user)

            messages.success(
                request,
                'Registration successful! Please complete your student profile.'
            )

            return redirect('students:complete_student_profile')

    else:
        form = UserRegistrationForm()

    return render(
        request,
        'registration/register.html',
        {'form': form}
    )


@login_required
def complete_student_profile(request):
    if request.user.is_staff:
        return redirect('students:dashboard')

    # If this account already has a profile, don't create another.
    if Student.objects.filter(user=request.user).exists():
        return redirect('students:student_dashboard')

    if request.method == 'POST':
        form = StudentForm(request.POST)

        if form.is_valid():
            with transaction.atomic():
                student = form.save(commit=False)
                student.user = request.user
                student.save()
                form.save_m2m()

            messages.success(
                request,
                'Your student profile has been saved successfully!'
            )

            return redirect('students:student_dashboard')

    else:
        form = StudentForm(
            initial={'email': request.user.email}
        )

    return render(
        request,
        'students/complete_profile.html',
        {'form': form}
    )




def staff_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('admin_login')

        if not request.user.is_staff:
            messages.error(
                request,
                'Access denied. Staff permissions are required.'
            )
            return redirect('students:dashboard')

        return view_func(request, *args, **kwargs)



def admin_login(request):
    return role_login(request, required_staff=True)


def student_login(request):
    return role_login(request, required_staff=False)



def role_login(request, required_staff):
    template_name = (
        'registration/admin_login.html'
        if required_staff
        else 'registration/student_login.html'
    )

    # Handle users who are already logged in

    # Handle users who are already logged in
    if request.user.is_authenticated:
        if request.user.is_staff:
            return redirect('students:dashboard')

        student = Student.objects.filter(
            user=request.user
        ).first()

        if student and not student.is_active:
            logout(request)
            messages.error(
                request,
                'Your student account is inactive. '
                'Please contact the administrator.'
            )
            return redirect('students:student_login')

        if student:
            return redirect('students:student_dashboard')

        return redirect('students:complete_student_profile')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        user = authenticate(
            request,
            username=username,
            password=password,
        )

        if user is None:
            messages.error(
                request,
                'Invalid username or password.'
            )


        elif user.is_staff != required_staff:

            messages.error(

                request,

                'This account cannot use this login page.'

            )
        elif not user.is_staff and Student.objects.filter(
                user=user,
                is_active=False
        ).exists():
            messages.error(
                request,
                'Your student account is inactive. '
                'Please contact the administrator.'
            )

        else:
            login(request, user)

            # Admins can continue to their intended destination.
            if user.is_staff:
                next_url = (
                    request.POST.get('next')
                    or request.GET.get('next')
                    or ''
                )

                if next_url and url_has_allowed_host_and_scheme(
                    next_url,
                    allowed_hosts={request.get_host()},
                    require_https=request.is_secure(),
                ):
                    return redirect(next_url)

                return redirect('students:dashboard')

            # Students must complete their profile before continuing.
            if not Student.objects.filter(user=user).exists():
                return redirect('students:complete_student_profile')

            next_url = (
                request.POST.get('next')
                or request.GET.get('next')
                or ''
            )

            if next_url and url_has_allowed_host_and_scheme(
                next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(next_url)

            return redirect('students:student_dashboard')

    return render(
        request,
        template_name,
        {'next': request.GET.get('next', '')},
    )





@login_required
def student_dashboard(request):
    # Staff users should use the admin/staff dashboard.
    if request.user.is_staff:
        return redirect('students:dashboard')

    try:
        student = Student.objects.select_related(
            'course_ref'
        ).get(user=request.user)
    except Student.DoesNotExist:
        student = None
        messages.warning(
            request,
            'Your student profile has not been linked yet. '
            'Please contact the administrator.'
        )

    # Block inactive students from accessing their dashboard.
    if student and not student.is_active:
        logout(request)
        messages.error(
            request,
            'Your student account is inactive. '
            'Please contact the administrator.'
        )
        return redirect('students:student_login')

    return render(
        request,
        'students/student_dashboard.html',
        {'student': student},
    )



@login_required
def mark_attendance(request):
    # Only staff/admin users can mark attendance.
    if not request.user.is_staff:
        messages.error(
            request,
            'Only administrators can mark attendance.'
        )
        return redirect('students:student_dashboard')

    selected_date = (
        request.POST.get('date')
        if request.method == 'POST'
        else request.GET.get('date')
    )

    attendance_date = (
        parse_date(selected_date)
        if selected_date
        else timezone.localdate()
    )

    if attendance_date is None:
        messages.error(request, 'Please select a valid date.')
        return redirect('students:mark_attendance')

    students = Student.objects.order_by('student_id')

    if request.method == 'POST':
        valid_statuses = {
            choice[0]
            for choice in Attendance.STATUS_CHOICES
        }

        saved_count = 0

        with transaction.atomic():
            for student in students:
                status = request.POST.get(
                    f'status_{student.pk}',
                    ''
                )

                remarks = request.POST.get(
                    f'remarks_{student.pk}',
                    ''
                ).strip()

                # Leave the record unchanged if no valid status
                # was submitted for this student.
                if status not in valid_statuses:
                    continue

                Attendance.objects.update_or_create(
                    student=student,
                    date=attendance_date,
                    defaults={
                        'status': status,
                        'remarks': remarks,
                        'marked_by': request.user,
                    }
                )
                saved_count += 1

        messages.success(
            request,
            f'Attendance saved for {saved_count} student(s).'
        )

        return redirect(
            f'/attendance/mark/?date={attendance_date.isoformat()}'
        )

    existing_records = {
        record.student_id: record
        for record in Attendance.objects.filter(
            date=attendance_date
        )
    }

    student_rows = []

    for student in students:
        record = existing_records.get(student.pk)

        student_rows.append({
            'student': student,
            'status': record.status if record else '',
            'remarks': record.remarks if record else '',
        })

    return render(
        request,
        'students/mark_attendance.html',
        {
            'student_rows': student_rows,
            'attendance_date': attendance_date,
        }
    )



@login_required
def attendance_list(request):
    if not request.user.is_staff:
        messages.error(
            request,
            'Only administrators can view all attendance records.'
        )
        return redirect('students:student_dashboard')

    selected_date = request.GET.get('date', '').strip()
    selected_status = request.GET.get('status', '').strip()
    search = request.GET.get('q', '').strip()
    start_date = request.GET.get('start_date', '').strip()
    end_date = request.GET.get('end_date', '').strip()
    selected_course = request.GET.get('course', '').strip()

    records = Attendance.objects.select_related(
        'student',
        'student__course_ref',
        'marked_by'
    ).all()

    # Existing single-date filter
    if selected_date:
        parsed_date = parse_date(selected_date)
        if parsed_date:
            records = records.filter(date=parsed_date)
        else:
            messages.error(request, 'Invalid date filter.')

    # New start-date filter
    if start_date:
        parsed_start_date = parse_date(start_date)
        if parsed_start_date:
            records = records.filter(date__gte=parsed_start_date)
        else:
            messages.error(request, 'Invalid start date.')

    # New end-date filter
    if end_date:
        parsed_end_date = parse_date(end_date)
        if parsed_end_date:
            records = records.filter(date__lte=parsed_end_date)
        else:
            messages.error(request, 'Invalid end date.')

    # Prevent a reversed date range
    if start_date and end_date:
        parsed_start = parse_date(start_date)
        parsed_end = parse_date(end_date)

        if parsed_start and parsed_end and parsed_start > parsed_end:
            messages.error(
                request,
                'Start date cannot be later than end date.'
            )
            records = records.none()

    # Existing status filter
    valid_statuses = {
        choice[0] for choice in Attendance.STATUS_CHOICES
    }

    if selected_status in valid_statuses:
        records = records.filter(status=selected_status)
    elif selected_status:
        messages.error(request, 'Invalid attendance status.')

    # Existing student search
    if search:
        records = records.filter(
            Q(student__student_id__icontains=search)
            | Q(student__first_name__icontains=search)
            | Q(student__last_name__icontains=search)
        )

    # New course filter
    courses = Course.objects.all().order_by('course_name')

    if selected_course:
        if selected_course.isdigit():
            records = records.filter(
                student__course_ref_id=int(selected_course)
            )
        else:
            messages.error(request, 'Invalid course filter.')

    # Summary counts now match the filtered records
    summary = records.aggregate(
        total=Count('id'),
        present=Count('id', filter=Q(status='Present')),
        absent=Count('id', filter=Q(status='Absent')),
        late=Count('id', filter=Q(status='Late')),
        excused=Count('id', filter=Q(status='Excused')),
    )

    total = summary['total'] or 0
    present = summary['present'] or 0

    summary['attendance_percentage'] = (
        round((present / total) * 100, 2)
        if total else 0
    )

    return render(
        request,
        'students/attendance_list.html',
        {
            'records': records,
            'summary': summary,
            'selected_date': selected_date,
            'selected_status': selected_status,
            'search': search,
            'start_date': start_date,
            'end_date': end_date,
            'selected_course': selected_course,
            'courses': courses,
            'status_choices': Attendance.STATUS_CHOICES,
        }
    )

@login_required
def student_attendance(request):
    if request.user.is_staff:
        return redirect('students:attendance_list')

    try:
        student = Student.objects.get(user=request.user)
    except Student.DoesNotExist:
        messages.warning(
            request,
            'Your student profile has not been linked yet.'
        )
        return redirect('students:complete_student_profile')

    records = Attendance.objects.filter(
        student=student
    ).order_by('-date')

    summary = records.aggregate(
        total=Count('id'),
        present=Count('id', filter=Q(status='Present')),
        absent=Count('id', filter=Q(status='Absent')),
        late=Count('id', filter=Q(status='Late')),
        excused=Count('id', filter=Q(status='Excused')),
    )

    return render(
        request,
        'students/student_attendance.html',
        {
            'student': student,
            'records': records,
            'summary': summary,
        }
    )



@login_required
def subject_create(request):
    if not request.user.is_staff:
        messages.error(request, 'Admin access is required.')
        return redirect('students:student_dashboard')

    if request.method == 'POST':
        form = SubjectForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, 'Subject created successfully.')
            return redirect('students:subject_create')
    else:
        form = SubjectForm()

    return render(
        request,
        'students/subject_form.html',
        {'form': form}
    )


@login_required
def exam_create(request):
    if not request.user.is_staff:
        messages.error(request, 'Admin access is required.')
        return redirect('students:student_dashboard')

    if request.method == 'POST':
        form = ExamForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, 'Exam created successfully.')
            return redirect('students:exam_create')
    else:
        form = ExamForm()

    return render(
        request,
        'students/exam_form.html',
        {'form': form}
    )




@login_required
def enter_marks(request):
    if not request.user.is_staff:
        messages.error(request, 'Admin access is required.')
        return redirect('students:student_dashboard')

    exam_id = (
        request.POST.get('exam')
        if request.method == 'POST'
        else request.GET.get('exam')
    )

    exams = Exam.objects.select_related(
        'subject', 'subject__course'
    ).all()

    selected_exam = None
    student_rows = []

    if exam_id:
        selected_exam = get_object_or_404(exams, pk=exam_id)

        students = Student.objects.filter(
            course_ref=selected_exam.subject.course
        ).order_by('student_id')

        existing_marks = {
            mark.student_id: mark
            for mark in Mark.objects.filter(exam=selected_exam)
        }

        if request.method == 'POST':
            saved_count = 0
            errors = []

            with transaction.atomic():
                for student in students:
                    raw_marks = request.POST.get(
                        f'marks_{student.pk}', ''
                    ).strip()

                    remarks = request.POST.get(
                        f'remarks_{student.pk}', ''
                    ).strip()

                    # Leave empty marks unchanged.
                    if raw_marks == '':
                        continue

                    # Only allow whole numbers.
                    if not raw_marks.isdigit():
                        errors.append(
                            f'Marks for {student.student_id} must '
                            'be a whole number.'
                        )
                        continue

                    marks_value = Decimal(raw_marks)

                    if marks_value > selected_exam.max_marks:
                        errors.append(
                            f'Marks for {student.student_id} must be '
                            f'between 0 and '
                            f'{selected_exam.max_marks:.0f}.'
                        )
                        continue

                    Mark.objects.update_or_create(
                        student=student,
                        exam=selected_exam,
                        defaults={
                            'marks_obtained': marks_value,
                            'remarks': remarks,
                            'entered_by': request.user,
                        }
                    )
                    saved_count += 1

            if errors:
                for error in errors:
                    messages.error(request, error)

            if saved_count:
                messages.success(
                    request,
                    f'Marks saved for {saved_count} student(s).'
                )

            if not errors:
                return redirect(
                    f'/results/enter/?exam={selected_exam.pk}'
                )

        # Reload saved marks so the form displays current values.
        existing_marks = {
            mark.student_id: mark
            for mark in Mark.objects.filter(exam=selected_exam)
        }

        for student in students:
            mark = existing_marks.get(student.pk)

            student_rows.append({
                'student': student,
                'marks': (
                    mark.marks_obtained
                    if mark else ''
                ),
                'remarks': mark.remarks if mark else '',
            })

    return render(
        request,
        'students/enter_marks.html',
        {
            'exams': exams,
            'selected_exam': selected_exam,
            'student_rows': student_rows,
        }
    )



@login_required
def results_list(request):
    if not request.user.is_staff:
        messages.error(request, 'Admin access is required.')
        return redirect('students:my_results')

    search = request.GET.get('q', '').strip()
    exam_id = request.GET.get('exam', '').strip()

    records = Mark.objects.select_related(
        'student',
        'exam',
        'exam__subject',
        'exam__subject__course',
    ).all()

    if search:
        records = records.filter(
            Q(student__student_id__icontains=search)
            | Q(student__first_name__icontains=search)
            | Q(student__last_name__icontains=search)
        )

    selected_exam = None

    if exam_id:
        selected_exam = Exam.objects.filter(pk=exam_id).first()
        if selected_exam:
            records = records.filter(exam=selected_exam)

    return render(
        request,
        'students/results_list.html',
        {
            'records': records,
            'exams': Exam.objects.select_related('subject').all(),
            'selected_exam': selected_exam,
            'search': search,
            'exam_id': exam_id,
        }
    )


@login_required
def my_results(request):
    if request.user.is_staff:
        return redirect('students:results_list')

    try:
        student = Student.objects.get(user=request.user)
    except Student.DoesNotExist:
        messages.warning(
            request,
            'Your student profile has not been linked yet.'
        )
        return redirect('students:complete_student_profile')

    records = Mark.objects.filter(
        student=student
    ).select_related(
        'exam',
        'exam__subject',
        'exam__subject__course',
    ).order_by('-exam__exam_date')

    return render(
        request,
        'students/my_results.html',
        {
            'student': student,
            'records': records,
        }
    )


@login_required
def edit_mark(request, pk):
    if not request.user.is_staff:
        messages.error(request, 'Admin access is required.')
        return redirect('students:results_list')

    mark = get_object_or_404(
        Mark.objects.select_related('student', 'exam'),
        pk=pk,
    )

    if request.method == 'POST':
        raw_marks = request.POST.get('marks_obtained', '').strip()
        remarks = request.POST.get('remarks', '').strip()

        try:
            from decimal import Decimal, InvalidOperation

            if not raw_marks.isdigit():
                raise ValueError('Marks must be a whole number.')

            marks_value = Decimal(raw_marks)

            if marks_value < 0 or marks_value > mark.exam.max_marks:
                raise ValueError(
                    f'Marks must be between 0 and '
                    f'{mark.exam.max_marks:.0f}.'
                )

        except (ValueError, InvalidOperation) as error:
            messages.error(request, str(error))
        else:
            mark.marks_obtained = marks_value
            mark.remarks = remarks
            mark.entered_by = request.user
            mark.save()

            messages.success(request, 'Marks updated successfully.')
            return redirect('students:results_list')

    return render(
        request,
        'students/edit_mark.html',
        {'mark': mark},
    )


@login_required
@require_POST
def delete_mark(request, pk):
    if not request.user.is_staff:
        messages.error(request, 'Admin access is required.')
        return redirect('students:results_list')

    mark = get_object_or_404(Mark, pk=pk)
    student_id = mark.student.student_id
    exam_name = mark.exam.exam_name

    mark.delete()

    messages.success(
        request,
        f'Marks deleted for {student_id} in {exam_name}.'
    )
    return redirect('students:results_list')



@login_required
def report_card(request, student_id):
    # Staff can view any student's report card.
    # Students can view only their own report card.
    if request.user.is_staff:
        student = get_object_or_404(Student, pk=student_id)
    else:
        try:
            student = request.user.student_profile
        except Student.DoesNotExist:
            messages.info(
                request,
                'Please complete your student profile first.'
            )
            return redirect('students:complete_student_profile')

        if student.pk != student_id:
            messages.error(
                request,
                'You are not allowed to view another student’s report card.'
            )
            return redirect('students:student_dashboard')

    marks = list(
        Mark.objects.filter(student=student)
        .select_related('exam', 'exam__subject', 'exam__subject__course')
        .order_by('exam__exam_date', 'exam__subject__subject_name')
    )

    total_obtained = sum(
        (mark.marks_obtained for mark in marks),
        Decimal('0')
    )
    total_maximum = sum(
        (mark.exam.max_marks for mark in marks),
        Decimal('0')
    )

    percentage = (
        (total_obtained * Decimal('100') / total_maximum).quantize(
            Decimal('0.01')
        )
        if total_maximum > 0
        else Decimal('0.00')
    )

    overall_result = (
        'Pass'
        if marks and all(mark.result_status == 'Pass' for mark in marks)
        else 'Fail' if marks else 'No Results'
    )

    return render(
        request,
        'students/report_card.html',
        {
            'student': student,
            'marks': marks,
            'total_obtained': total_obtained,
            'total_maximum': total_maximum,
            'percentage': percentage,
            'overall_result': overall_result,
        }
    )



@login_required
def statistics_dashboard(request):
    # Only staff can access the management statistics.
    if not request.user.is_staff:
        messages.error(request, 'Admin access is required.')
        return redirect('students:student_dashboard')

    # Summary statistics
    total_students = Student.objects.count()
    total_courses = Course.objects.count()
    total_subjects = Subject.objects.count()
    total_exams = Exam.objects.count()
    total_results = Mark.objects.count()

    # Attendance statistics
    attendance_statuses = ['Present', 'Absent', 'Late', 'Excused']

    attendance_counts = {
        status: Attendance.objects.filter(status=status).count()
        for status in attendance_statuses
    }

    total_attendance = sum(attendance_counts.values())

    attendance_rate = (
        round(attendance_counts['Present'] * 100 / total_attendance, 2)
        if total_attendance else 0
    )

    # Average marks obtained for each subject
    subject_averages = list(
        Mark.objects.values(
            'exam__subject__subject_name'
        ).annotate(
            average_marks=Avg('marks_obtained')
        ).order_by(
            'exam__subject__subject_name'
        )
    )

    subject_labels = [
        item['exam__subject__subject_name']
        for item in subject_averages
    ]

    average_marks_data = [
        round(float(item['average_marks'] or 0), 2)
        for item in subject_averages
    ]
    # Count students with recorded attendance below 75%
    attendance_students = (
        Student.objects
        .annotate(
            total_days=Count('attendance_records'),
            present_days=Count(
                'attendance_records',
                filter=Q(attendance_records__status='Present')
            ),
        )
        .filter(total_days__gt=0)
    )

    low_attendance_count = sum(
        1
        for student in attendance_students
        if student.present_days * 100 < student.total_days * 75
    )
    context = {
        'total_students': total_students,
        'total_courses': total_courses,
        'total_subjects': total_subjects,
        'total_exams': total_exams,
        'total_results': total_results,
        'attendance_counts': attendance_counts,
        'total_attendance': total_attendance,
        'attendance_rate': attendance_rate,
        'attendance_labels': attendance_statuses,
        'attendance_data': [
            attendance_counts[status]
            for status in attendance_statuses
        ],
        'subject_labels': subject_labels,
        'average_marks_data': average_marks_data,
        'low_attendance_count': low_attendance_count,
    }

    return render(
        request,
        'students/statistics_dashboard.html',
        context,
    )



def is_fee_admin(user):
    return user.is_authenticated and user.is_staff



@login_required
@user_passes_test(is_fee_admin)
def fee_list(request):
    fees = FeeRecord.objects.filter(
        is_deleted=False
    ).select_related('student')

    # Search fields
    search_query = request.GET.get('q', '').strip()
    if search_query:
        fees = fees.filter(
            Q(fee_type__icontains=search_query)
            | Q(academic_year__icontains=search_query)
            | Q(student__user__username__icontains=search_query)
            | Q(student__user__first_name__icontains=search_query)
            | Q(student__user__last_name__icontains=search_query)
        )

    # Dropdown filters
    selected_status = request.GET.get('status', '').strip()
    selected_year = request.GET.get('year', '').strip()
    selected_fee_type = request.GET.get('fee_type', '').strip()

    if selected_year:
        fees = fees.filter(academic_year=selected_year)

    if selected_fee_type:
        fees = fees.filter(fee_type=selected_fee_type)

    # Calculate paid amount and balance in the database
    fees = fees.annotate(
        total_paid=Coalesce(
            Sum('payments__amount'),
            Decimal('0.00'),
            output_field=DecimalField(
                max_digits=12,
                decimal_places=2
            )
        )
    ).annotate(
        outstanding=F('total_amount') - F('total_paid')
    )

    if selected_status == 'Paid':
        fees = fees.filter(outstanding__lte=Decimal('0.00'))
    elif selected_status == 'Partially Paid':
        fees = fees.filter(
            total_paid__gt=Decimal('0.00'),
            outstanding__gt=Decimal('0.00')
        )
    elif selected_status == 'Pending':
        fees = fees.filter(total_paid=Decimal('0.00'))

    # Dropdown choices
    academic_years = (
        FeeRecord.objects.order_by('academic_year')
        .values_list('academic_year', flat=True)
        .distinct()
    )

    fee_types = (
        FeeRecord.objects.order_by('fee_type')
        .values_list('fee_type', flat=True)
        .distinct()
    )

    # Summary totals remain for all fee records
    all_fees = FeeRecord.objects.filter(is_deleted=False)
    total_fees = (
        all_fees.aggregate(total=Sum('total_amount'))['total']
        or Decimal('0.00')
    )
    total_paid = (
            FeePayment.objects
            .filter(fee_record__is_deleted=False)
            .aggregate(total=Sum('amount'))['total']
            or Decimal('0.00')
    )

    # Paginate filtered results
    paginator = Paginator(fees, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'fees': page_obj,
        'page_obj': page_obj,
        'search_query': search_query,
        'selected_status': selected_status,
        'selected_year': selected_year,
        'selected_fee_type': selected_fee_type,
        'academic_years': academic_years,
        'fee_types': fee_types,
        'total_fees': total_fees,
        'total_paid': total_paid,
        'total_balance': total_fees - total_paid,
    }

    return render(
        request,
        'students/fee_list.html',
        context
    )


@login_required
@user_passes_test(is_fee_admin)
def assign_fee(request):
    if request.method == 'POST':
        form = FeeRecordForm(request.POST)

        if form.is_valid():
            fee = form.save()
            messages.success(
                request,
                f'Fee assigned successfully to {fee.student}.'
            )
            return redirect('students:fee_list')
    else:
        form = FeeRecordForm()

    return render(
        request,
        'students/assign_fee.html',
        {'form': form}
    )

@login_required
@user_passes_test(is_fee_admin)
def edit_fee(request, fee_id):
    fee = get_object_or_404(
        FeeRecord,
        pk=fee_id,
        is_deleted=False
    )
    if request.method == 'POST':
        form = FeeRecordForm(request.POST, instance=fee)

        if form.is_valid():
            updated_fee = form.save(commit=False)

            # Never allow the fee total to fall below
            # the amount already collected.
            if updated_fee.total_amount < fee.amount_paid:
                form.add_error(
                    'total_amount',
                    'The total fee cannot be less than the amount '
                    'already paid (₹'
                    f'{fee.amount_paid:.2f}).'
                )
            else:
                updated_fee.save()
                messages.success(
                    request,
                    'Fee record updated successfully.'
                )
                return redirect('students:fee_list')
    else:
        form = FeeRecordForm(instance=fee)

    return render(
        request,
        'students/edit_fee.html',
        {
            'form': form,
            'fee': fee,
        }
    )


@login_required
@user_passes_test(is_fee_admin)
@require_POST
def delete_fee(request, fee_id):
    fee = get_object_or_404(
        FeeRecord,
        pk=fee_id,
        is_deleted=False
    )

    # Soft delete: preserve the record and all its payments.
    fee.is_deleted = True
    fee.deleted_at = timezone.now()
    fee.save(update_fields=['is_deleted', 'deleted_at'])

    messages.success(
        request,
        f'{fee.fee_type} was moved to the Recycle Bin. '
        'Its payment history and receipts have been preserved.'
    )

    return redirect('students:fee_list')



@login_required
@user_passes_test(is_fee_admin)
def record_fee_payment(request, fee_id):
    if request.method == 'POST':
        with transaction.atomic():
            fee = get_object_or_404(
                FeeRecord.objects.select_for_update(),
                pk=fee_id,
                is_deleted=False
            )

            form = FeePaymentForm(
                request.POST,
                fee_record=fee
            )

            if form.is_valid():
                payment = form.save(commit=False)
                payment.fee_record = fee

                if payment.amount > fee.balance:
                    form.add_error(
                        'amount',
                        'Payment exceeds the outstanding balance.'
                    )
                else:
                    payment.save()
                    messages.success(
                        request,
                        f'Payment recorded. Receipt: {payment.receipt_number}'
                    )
                    return redirect(
                        'students:fee_receipt',
                        payment_id=payment.pk
                    )
    else:

        fee = get_object_or_404(
            FeeRecord,
            pk=fee_id,
            is_deleted=False
        )
        form = FeePaymentForm(fee_record=fee)

    return render(
        request,
        'students/record_payment.html',
        {'fee': fee, 'form': form}
    )


@login_required
@user_passes_test(is_fee_admin)
def fee_payment_history(request):
    payments = FeePayment.objects.select_related(
        'fee_record',
        'fee_record__student'
    ).all()

    return render(
        request,
        'students/payment_history.html',
        {'payments': payments}
    )


@login_required
@user_passes_test(is_fee_admin)
def fee_receipt(request, payment_id):
    payment = get_object_or_404(
        FeePayment.objects.select_related(
            'fee_record',
            'fee_record__student'
        ),
        pk=payment_id
    )

    fee = payment.fee_record

    context = {
        'payment': payment,
        'fee': fee,
        'student': fee.student,
    }

    return render(
        request,
        'students/fee_receipt.html',
        context
    )




@login_required
def student_fee_balances(request):
    # Find the student profile linked to the logged-in user
    student = get_object_or_404(
        Student,
        user=request.user
    )

    # Show only this student's fee records
    fees = (
        FeeRecord.objects
        .filter(student=student, is_deleted=False)
        .prefetch_related('payments')
        .order_by('-created_at')
    )

    total_fees = sum(
        (fee.total_amount for fee in fees),
        Decimal('0.00')
    )

    total_paid = sum(
        (fee.amount_paid for fee in fees),
        Decimal('0.00')
    )

    total_balance = total_fees - total_paid

    context = {
        'student': student,
        'fees': fees,
        'total_fees': total_fees,
        'total_paid': total_paid,
        'total_balance': total_balance,
    }

    return render(
        request,
        'students/student_fee_balances.html',
        context
    )


@login_required
def student_fee_payment_history(request):
    # Find the logged-in student's profile
    student = get_object_or_404(
        Student,
        user=request.user
    )

    # Never show payments belonging to another student
    payments = (
        FeePayment.objects
        .filter(fee_record__student=student)
        .select_related('fee_record')
        .order_by('-payment_date', '-created_at')
    )

    return render(
        request,
        'students/student_fee_payment_history.html',
        {
            'student': student,
            'payments': payments,
        }
    )


@login_required
@user_passes_test(is_fee_admin)
def fee_recycle_bin(request):
    deleted_fees = (
        FeeRecord.objects
        .filter(is_deleted=True)
        .select_related('student')
        .order_by('-deleted_at')
    )

    return render(
        request,
        'students/fee_recycle_bin.html',
        {'deleted_fees': deleted_fees}
    )


@login_required
@user_passes_test(is_fee_admin)
@require_POST
def restore_fee(request, fee_id):
    fee = get_object_or_404(
        FeeRecord,
        pk=fee_id,
        is_deleted=True
    )

    fee.is_deleted = False
    fee.deleted_at = None
    fee.save(update_fields=['is_deleted', 'deleted_at'])

    messages.success(
        request,
        f'{fee.fee_type} was restored successfully.'
    )

    return redirect('students:fee_recycle_bin')



@login_required
def attendance_report(request):
    if not request.user.is_staff:
        messages.error(
            request,
            'Only administrators can view attendance reports.'
        )
        return redirect('students:student_dashboard')

    start_date = request.GET.get('start_date', '').strip()
    end_date = request.GET.get('end_date', '').strip()
    selected_course = request.GET.get('course', '').strip()
    search = request.GET.get('q', '').strip()

    records = Attendance.objects.all()

    # Filter by date range
    if start_date:
        parsed_start = parse_date(start_date)
        if parsed_start:
            records = records.filter(date__gte=parsed_start)
        else:
            messages.error(request, 'Invalid start date.')

    if end_date:
        parsed_end = parse_date(end_date)
        if parsed_end:
            records = records.filter(date__lte=parsed_end)
        else:
            messages.error(request, 'Invalid end date.')

    # Filter by course
    if selected_course:
        if selected_course.isdigit():
            records = records.filter(
                student__course_ref_id=int(selected_course)
            )
        else:
            messages.error(request, 'Invalid course filter.')

    # Filter by student name or ID
    if search:
        records = records.filter(
            Q(student__student_id__icontains=search)
            | Q(student__first_name__icontains=search)
            | Q(student__last_name__icontains=search)
        )

    # One summary row per student who has matching attendance records
    student_reports = (
        records.values(
            'student_id',
            'student__student_id',
            'student__first_name',
            'student__last_name',
            'student__course',
            'student__course_ref__course_name',
        )
        .annotate(
            total=Count('id'),
            present=Count('id', filter=Q(status='Present')),
            absent=Count('id', filter=Q(status='Absent')),
            late=Count('id', filter=Q(status='Late')),
            excused=Count('id', filter=Q(status='Excused')),
        )
        .order_by('student__student_id')
    )

    # Calculate percentage in Python to avoid database-specific
    # division behavior.
    report_rows = []

    for row in student_reports:
        row['attendance_percentage'] = (
            round(row['present'] / row['total'] * 100, 2)
            if row['total']
            else 0
        )
        report_rows.append(row)

    courses = Course.objects.all().order_by('course_name')

    context = {
        'student_reports': report_rows,
        'start_date': start_date,
        'end_date': end_date,
        'selected_course': selected_course,
        'search': search,
        'courses': courses,
    }

    return render(
        request,
        'students/attendance_report.html',
        context
    )



@login_required
def export_attendance_report(request):
    if not request.user.is_staff:
        messages.error(
            request,
            'Only administrators can export attendance reports.'
        )
        return redirect('students:student_dashboard')

    start_date = request.GET.get('start_date', '').strip()
    end_date = request.GET.get('end_date', '').strip()
    selected_course = request.GET.get('course', '').strip()
    selected_status = request.GET.get('status', '').strip()
    search = request.GET.get('q', '').strip()

    records = Attendance.objects.select_related(
        'student',
        'student__course_ref',
        'marked_by'
    ).all()

    # Apply date filters
    if start_date:
        parsed_start = parse_date(start_date)
        if not parsed_start:
            messages.error(request, 'Invalid start date.')
            return redirect('students:attendance_report')
        records = records.filter(date__gte=parsed_start)

    if end_date:
        parsed_end = parse_date(end_date)
        if not parsed_end:
            messages.error(request, 'Invalid end date.')
            return redirect('students:attendance_report')
        records = records.filter(date__lte=parsed_end)

    # Validate the date range
    if start_date and end_date:
        if parsed_start > parsed_end:
            messages.error(
                request,
                'Start date cannot be later than end date.'
            )
            return redirect('students:attendance_report')

    # Apply status filter
    valid_statuses = {
        choice[0] for choice in Attendance.STATUS_CHOICES
    }

    if selected_status:
        if selected_status not in valid_statuses:
            messages.error(request, 'Invalid attendance status.')
            return redirect('students:attendance_report')
        records = records.filter(status=selected_status)

    # Apply course filter
    if selected_course:
        if not selected_course.isdigit():
            messages.error(request, 'Invalid course filter.')
            return redirect('students:attendance_report')
        records = records.filter(
            student__course_ref_id=int(selected_course)
        )

    # Apply student search
    if search:
        records = records.filter(
            Q(student__student_id__icontains=search)
            | Q(student__first_name__icontains=search)
            | Q(student__last_name__icontains=search)
        )

    # Build CSV response
    response = HttpResponse(
        content_type='text/csv; charset=utf-8'
    )
    response['Content-Disposition'] = (
        'attachment; filename="attendance_report.csv"'
    )
    response.write('\ufeff')  # Helps Excel display UTF-8 correctly.

    writer = csv.writer(response)
    writer.writerow([
        'Date',
        'Student ID',
        'Student Name',
        'Course',
        'Status',
        'Remarks',
        'Marked By',
    ])

    for record in records.order_by(
        '-date', 'student__student_id'
    ):
        student = record.student
        course_name = (
            student.course_ref.course_name
            if student.course_ref
            else student.course
        )
        marked_by = (
            record.marked_by.username
            if record.marked_by
            else ''
        )

        writer.writerow([
            record.date.strftime('%Y-%m-%d'),
            student.student_id,
            f'{student.first_name} {student.last_name}',
            course_name,
            record.status,
            record.remarks,
            marked_by,
        ])

    return response


def _individual_attendance_context(student, request):
    start_date = request.GET.get('start_date', '').strip()
    end_date = request.GET.get('end_date', '').strip()

    records = Attendance.objects.filter(
        student=student
    ).select_related(
        'student',
        'student__course_ref',
        'marked_by'
    )

    # Apply start-date filter
    if start_date:
        parsed_start = parse_date(start_date)
        if parsed_start:
            records = records.filter(date__gte=parsed_start)
        else:
            messages.error(request, 'Invalid start date.')

    # Apply end-date filter
    if end_date:
        parsed_end = parse_date(end_date)
        if parsed_end:
            records = records.filter(date__lte=parsed_end)
        else:
            messages.error(request, 'Invalid end date.')

    # Reject reversed date ranges
    parsed_start = parse_date(start_date) if start_date else None
    parsed_end = parse_date(end_date) if end_date else None

    if parsed_start and parsed_end and parsed_start > parsed_end:
        messages.error(
            request,
            'Start date cannot be later than end date.'
        )
        records = records.none()

    summary = records.aggregate(
        total=Count('id'),
        present=Count('id', filter=Q(status='Present')),
        absent=Count('id', filter=Q(status='Absent')),
        late=Count('id', filter=Q(status='Late')),
        excused=Count('id', filter=Q(status='Excused')),
    )

    total = summary['total'] or 0
    present = summary['present'] or 0

    summary['attendance_percentage'] = (
        round(present * 100 / total, 2)
        if total else 0
    )

    return {
        'student': student,
        'records': records.order_by('-date'),
        'summary': summary,
        'start_date': start_date,
        'end_date': end_date,
    }


@login_required
def individual_attendance_report(request, student_id):
    if not request.user.is_staff:
        messages.error(
            request,
            'Only administrators can view individual student reports.'
        )
        return redirect('students:student_dashboard')

    student = get_object_or_404(
        Student.objects.select_related('course_ref'),
        pk=student_id
    )

    context = _individual_attendance_context(student, request)

    return render(
        request,
        'students/individual_attendance_report.html',
        context
    )


@login_required
def my_attendance_report(request):
    if request.user.is_staff:
        return redirect('students:attendance_report')

    student = get_object_or_404(
        Student.objects.select_related('course_ref'),
        user=request.user
    )

    context = _individual_attendance_context(student, request)

    return render(
        request,
        'students/individual_attendance_report.html',
        context
    )



@login_required
def low_attendance_students(request):
    if not request.user.is_staff:
        messages.error(
            request,
            "Only administrators can view low-attendance alerts."
        )
        return redirect('students:student_dashboard')

    students = (
        Student.objects
        .select_related('course_ref')
        .annotate(
            total_days=Count('attendance_records'),
            present_days=Count(
                'attendance_records',
                filter=Q(attendance_records__status='Present')
            ),
        )
        .filter(total_days__gt=0)
        .order_by('student_id')
    )

    low_attendance = []

    for student in students:
        percentage = round(
            student.present_days * 100 / student.total_days,
            2
        )

        if percentage < 75:
            student.attendance_percentage = percentage
            low_attendance.append(student)

    context = {
        'low_attendance': low_attendance,
        'threshold': 75,
        'total_low_attendance': len(low_attendance),
    }

    return render(
        request,
        'students/low_attendance_students.html',
        context
    )




@login_required
def individual_attendance_report_pdf(request, student_id):
    # Find the requested student.
    if request.user.is_staff:
        student = get_object_or_404(
            Student.objects.select_related('course_ref'),
            pk=student_id
        )
    else:
        student = get_object_or_404(
            Student.objects.select_related('course_ref'),
            pk=student_id,
            user=request.user
        )

    # Reuse the existing report calculations and date filters.
    context = _individual_attendance_context(student, request)

    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name='ReportTitle',
        parent=styles['Title'],
        alignment=TA_CENTER,
        textColor=colors.HexColor('#1D4ED8'),
        spaceAfter=12,
    ))

    story = []

    story.append(Paragraph(
        'Individual Student Attendance Report',
        styles['ReportTitle']
    ))

    story.append(Paragraph(
        f"<b>Student ID:</b> {escape(str(student.student_id))}",
        styles['Normal']
    ))

    story.append(Paragraph(
        f"<b>Student Name:</b> "
        f"{escape(student.first_name)} {escape(student.last_name)}",
        styles['Normal']
    ))

    course_name = (
        student.course_ref.course_name
        if student.course_ref
        else student.course
    )

    story.append(Paragraph(
        f"<b>Course:</b> {escape(str(course_name))}",
        styles['Normal']
    ))

    story.append(Paragraph(
        f"<b>Report Period:</b> "
        f"{escape(context['start_date'] or 'All dates')} to "
        f"{escape(context['end_date'] or 'All dates')}",
        styles['Normal']
    ))

    story.append(Spacer(1, 10))

    summary = context['summary']

    summary_data = [
        ['Total', 'Present', 'Absent', 'Late', 'Excused',
         'Attendance Percentage'],
        [
            str(summary['total'] or 0),
            str(summary['present'] or 0),
            str(summary['absent'] or 0),
            str(summary['late'] or 0),
            str(summary['excused'] or 0),
            f"{summary['attendance_percentage']}%",
        ],
    ]

    summary_table = Table(
        summary_data,
        colWidths=[25 * mm, 25 * mm, 25 * mm, 25 * mm,
                   25 * mm, 45 * mm],
    )

    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1D4ED8')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('PADDING', (0, 0), (-1, -1), 7),
    ]))

    story.append(summary_table)
    story.append(Spacer(1, 15))

    story.append(Paragraph('Attendance History', styles['Heading2']))
    story.append(Spacer(1, 6))

    history_data = [[
        'Date', 'Status', 'Remarks', 'Marked By'
    ]]

    for record in context['records']:
        marked_by = (
            record.marked_by.username
            if record.marked_by
            else '-'
        )

        history_data.append([
            record.date.strftime('%d %b %Y'),
            escape(str(record.status)),
            Paragraph(
                escape(record.remarks or '-'),
                styles['BodyText']
            ),
            Paragraph(escape(str(marked_by)), styles['BodyText']),
        ])

    if len(history_data) == 1:
        history_data.append(['-', 'No records', '-', '-'])

    history_table = Table(
        history_data,
        colWidths=[35 * mm, 35 * mm, 125 * mm, 45 * mm],
        repeatRows=1,
    )

    history_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#212529')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1),
         [colors.white, colors.HexColor('#F3F4F6')]),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))

    story.append(history_table)

    document.build(story)

    pdf = buffer.getvalue()
    buffer.close()

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="attendance_{student.student_id}.pdf"'
    )

    return response


def admin_register(request):
    if request.user.is_authenticated:
        if request.user.is_staff:
            return redirect('students:dashboard')
        return redirect('students:student_dashboard')

    if request.method == 'POST':
        form = AdminRegisterForm(request.POST)

        if form.is_valid():
            user = form.save(commit=False)

            # Keep this account inactive until an admin approves it.
            user.is_staff = False
            user.is_superuser = False
            user.is_active = False
            user.save()

            AdminRegistrationRequest.objects.create(
                user=user,
                status='Pending'
            )

            messages.success(
                request,
                'Your admin registration request has been submitted. '
                'You can log in after an administrator approves it.'
            )

            return redirect('admin_login')
    else:
        form = AdminRegisterForm()

    return render(
        request,
        'registration/admin_register.html',
        {'form': form}
    )


@login_required
def admin_registration_requests(request):
    if not request.user.is_staff:
        messages.error(
            request,
            'You are not authorized to manage admin requests.'
        )
        return redirect('students:student_dashboard')

    requests_list = AdminRegistrationRequest.objects.select_related(
        'user'
    ).order_by('-requested_at')

    return render(
        request,
        'students/admin_registration_requests.html',
        {'requests_list': requests_list}
    )


@login_required
def approve_admin_request(request, request_id):
    if request.method != 'POST':
        return redirect('students:admin_registration_requests')

    if not request.user.is_superuser:
        messages.error(
            request,
            'Only a superuser can approve admin registration requests.'
        )
        return redirect('students:admin_registration_requests')

    registration_request = get_object_or_404(
        AdminRegistrationRequest,
        pk=request_id,
        status='Pending'
    )

    new_admin = registration_request.user
    new_admin.is_active = True
    new_admin.is_staff = True
    new_admin.is_superuser = False
    new_admin.save(
        update_fields=['is_active', 'is_staff', 'is_superuser']
    )

    registration_request.status = 'Approved'
    registration_request.save(update_fields=['status'])

    messages.success(
        request,
        f'Admin account for {new_admin.username} has been approved.'
    )

    return redirect('students:admin_registration_requests')


@login_required
def reject_admin_request(request, request_id):
    if request.method != 'POST':
        return redirect('students:admin_registration_requests')

    if not request.user.is_superuser:
        messages.error(
            request,
            'Only a superuser can reject admin registration requests.'
        )
        return redirect('students:admin_registration_requests')

    registration_request = get_object_or_404(
        AdminRegistrationRequest,
        pk=request_id,
        status='Pending'
    )

    registration_request.status = 'Rejected'
    registration_request.save(update_fields=['status'])

    messages.success(
        request,
        f'Registration request for '
        f'{registration_request.user.username} was rejected.'
    )

    return redirect('students:admin_registration_requests')


def send_low_attendance_alert(student):
    attendance_records = student.attendance_records.all()
    total_days = attendance_records.count()

    if total_days == 0:
        return 'no_records'

    present_days = attendance_records.filter(
        status='Present'
    ).count()

    attendance_percentage = (present_days / total_days) * 100

    # Get or create the notification tracking record
    alert, created = LowAttendanceAlert.objects.get_or_create(
        student=student
    )

    alert.attendance_percentage = round(attendance_percentage, 2)

    # Attendance is not below 75%
    if attendance_percentage >= 75:
        alert.alert_sent = False
        alert.save(update_fields=[
            'attendance_percentage',
            'alert_sent',
        ])
        return 'not_eligible'

    # Prevent duplicate emails
    if alert.alert_sent:
        alert.save(update_fields=['attendance_percentage'])
        return 'already_sent'

    # Check the student's email address
    if not student.email or not student.email.strip():
        alert.save(update_fields=['attendance_percentage'])
        return 'no_email'

    print(
        "WEB EMAIL CONFIG:",
        repr(settings.DEFAULT_FROM_EMAIL),
        bool(settings.EMAIL_HOST_USER),
        bool(settings.EMAIL_HOST_PASSWORD),
        flush=True,
    )
    # Send the notification
    send_mail(
        subject='Low Attendance Alert',
        message=(
            f'Hello {student.first_name} {student.last_name},\n\n'
            f'Your current attendance is {attendance_percentage:.2f}%.\n'
            'Your attendance is below the required 75%.\n'
            'Please attend classes regularly.\n\n'
            'Regards,\n'
            'Student Management System'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[student.email],
        fail_silently=False,
    )

    # Mark as sent only after the email send call succeeds
    alert.alert_sent = True
    alert.attendance_percentage = round(attendance_percentage, 2)
    alert.last_sent_at = timezone.now()
    alert.save(update_fields=[
        'alert_sent',
        'attendance_percentage',
        'last_sent_at',
    ])

    return 'sent'




@staff_member_required
def send_low_attendance_alerts(request):
    if request.method != 'POST':
        return redirect('students:low_attendance_students')

    counts = {
        'sent': 0,
        'already_sent': 0,
        'not_eligible': 0,
        'no_records': 0,
        'no_email': 0,
        'failed': 0,
    }

    for student in Student.objects.all().iterator():
        try:
            result = send_low_attendance_alert(student)
            counts[result] += 1

        except Exception as e:
            counts['failed'] += 1
            print(
                f"EMAIL ERROR for {student.student_id}: "
                f"{type(e).__name__}: {e}",
                flush=True
            )

    messages.success(
        request,
        (
            f"Emails sent: {counts['sent']}. "
            f"Already notified: {counts['already_sent']}. "
            f"Not eligible: {counts['not_eligible']}. "
            f"No attendance records: {counts['no_records']}. "
            f"Missing email: {counts['no_email']}. "
            f"Failed: {counts['failed']}."
        )
    )

    return redirect('students:low_attendance_students')






import logging

logger = logging.getLogger(__name__)

class StudentPasswordResetView(auth_views.PasswordResetView):
    template_name = 'registration/password_reset_form.html'
    email_template_name = 'registration/password_reset_email.html'
    subject_template_name = 'registration/password_reset_subject.txt'
    form_class = StudentPasswordResetForm
    success_url = reverse_lazy('password_reset_done')

    def form_valid(self, form):
        users = list(form.get_users(form.cleaned_data['email']))
        logger.warning("PASSWORD RESET: eligible account count = %s", len(users))
        logger.warning("PASSWORD RESET: email backend = %s",
                       __import__('django.conf', fromlist=['settings']).settings.EMAIL_BACKEND)

        response = super().form_valid(form)

        logger.warning("PASSWORD RESET: request processing finished")
        return response

    def form_invalid(self, form):
        logger.warning("Password reset form is invalid: %s", form.errors)
        return super().form_invalid(form)


class AdminPasswordResetView(auth_views.PasswordResetView):
    template_name = 'registration/password_reset_form.html'
    email_template_name = 'registration/password_reset_email.html'
    subject_template_name = 'registration/password_reset_subject.txt'
    form_class = AdminPasswordResetForm
    success_url = reverse_lazy('password_reset_done')