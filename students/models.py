
import re

from django.db import models
from django.contrib.auth.models import User


class Student(models.Model):
    GENDER_CHOICES = [
        ('Male', 'Male'),
        ('Female', 'Female'),
        ('Other', 'Other'),
    ]

    student_id = models.CharField(max_length=20, unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=10, unique=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    course = models.CharField(max_length=100)
    is_active=models.BooleanField(default=True)
    course_ref = models.ForeignKey(
        'Course',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='students'
    )

    date_of_birth = models.DateField()
    address = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='student_profile'
    )

    class Meta:
        ordering = ['student_id']

    @classmethod
    def generate_student_id(cls):
        # Read existing IDs without changing any records.
        existing_ids = cls.objects.values_list(
            'student_id', flat=True
        )

        highest_number = 0

        # Supports existing IDs like 101 and new IDs like STU107.
        for existing_id in existing_ids:
            match = re.fullmatch(
                r'(?:STU)?(\d+)',
                existing_id.strip(),
                re.IGNORECASE
            )

            if match:
                number = int(match.group(1))
                highest_number = max(highest_number, number)

        next_number = highest_number + 1

        # Skip any ID that already exists.
        while True:
            candidate = f'STU{next_number:03d}'

            if not cls.objects.filter(student_id=candidate).exists():
                return candidate

            next_number += 1

    def save(self, *args, **kwargs):
        # Generate an ID only when it is missing.
        if not self.student_id or not self.student_id.strip():
            self.student_id = self.generate_student_id()

        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.student_id} - "
            f"{self.first_name} {self.last_name}"
        )


class Course(models.Model):
    course_code = models.CharField(max_length=20, unique=True)
    course_name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['course_name']

    def __str__(self):
        return f"{self.course_code} - {self.course_name}"



class Attendance(models.Model):
    STATUS_CHOICES = [
        ('Present', 'Present'),
        ('Absent', 'Absent'),
        ('Late', 'Late'),
        ('Excused', 'Excused'),
    ]

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='attendance_records'
    )

    date = models.DateField()

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='Present'
    )

    remarks = models.CharField(
        max_length=255,
        blank=True
    )

    marked_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='marked_attendance_records'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', 'student__student_id']
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'date'],
                name='unique_student_attendance_per_day'
            )
        ]

    def __str__(self):
        return (
            f"{self.student.student_id} - "
            f"{self.date} - {self.status}"
        )



from decimal import Decimal


class Subject(models.Model):
    course = models.ForeignKey(
        Course,
        on_delete=models.PROTECT,
        related_name='subjects'
    )
    subject_code = models.CharField(max_length=20, unique=True)
    subject_name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['course__course_name', 'subject_name']

    def __str__(self):
        return f"{self.subject_code} - {self.subject_name}"


class Exam(models.Model):
    subject = models.ForeignKey(
        Subject,
        on_delete=models.PROTECT,
        related_name='exams'
    )
    exam_name = models.CharField(max_length=100)
    exam_date = models.DateField()
    max_marks = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=Decimal('100.00')
    )
    pass_marks = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=Decimal('35.00')
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-exam_date', 'exam_name']
        constraints = [
            models.UniqueConstraint(
                fields=['subject', 'exam_name', 'exam_date'],
                name='unique_subject_exam_date'
            ),
            models.CheckConstraint(
                condition=models.Q(max_marks__gt=0),
                name='exam_max_marks_positive'
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(pass_marks__gte=0)
                    & models.Q(pass_marks__lte=models.F('max_marks'))
                ),
                name='exam_pass_marks_valid'
            ),
        ]

    def __str__(self):
        return f"{self.exam_name} - {self.subject.subject_name}"


class Mark(models.Model):
    student = models.ForeignKey(
        Student,
        on_delete=models.PROTECT,
        related_name='marks'
    )
    exam = models.ForeignKey(
        Exam,
        on_delete=models.PROTECT,
        related_name='marks'
    )
    marks_obtained = models.DecimalField(
        max_digits=7,
        decimal_places=2
    )
    remarks = models.CharField(max_length=255, blank=True)
    entered_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='entered_marks'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['student__student_id', 'exam__exam_date']
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'exam'],
                name='unique_student_exam_mark'
            ),
            models.CheckConstraint(
                condition=models.Q(marks_obtained__gte=0),
                name='marks_obtained_nonnegative'
            ),
        ]

    @property
    def percentage(self):
        if not self.exam.max_marks:
            return Decimal('0.00')

        return (
            self.marks_obtained
            * Decimal('100')
            / self.exam.max_marks
        ).quantize(Decimal('0.01'))

    @property
    def result_status(self):
        if self.marks_obtained >= self.exam.pass_marks:
            return 'Pass'
        return 'Fail'

    @property
    def grade(self):
        percentage = self.percentage

        if self.result_status == 'Fail':
            return 'F'
        if percentage >= Decimal('90'):
            return 'A+'
        if percentage >= Decimal('80'):
            return 'A'
        if percentage >= Decimal('70'):
            return 'B'
        if percentage >= Decimal('60'):
            return 'C'
        if percentage >= Decimal('50'):
            return 'D'
        return 'E'

    def __str__(self):
        return (
            f"{self.student.student_id} - "
            f"{self.exam} - {self.marks_obtained}"
        )



from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator


class FeeRecord(models.Model):
    student = models.ForeignKey(
        'students.Student',
        on_delete=models.PROTECT,
        related_name='fee_records'
    )
    fee_type = models.CharField(max_length=100)
    academic_year = models.CharField(max_length=20)
    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def amount_paid(self):
        return self.payments.aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')

    @property
    def balance(self):
        return self.total_amount - self.amount_paid

    @property
    def payment_status(self):
        if self.balance <= Decimal('0.00'):
            return 'Paid'
        elif self.amount_paid > Decimal('0.00'):
            return 'Partially Paid'
        return 'Pending'

    def __str__(self):
        return f'{self.student} - {self.fee_type}'


class FeePayment(models.Model):
    PAYMENT_METHODS = [
        ('Cash', 'Cash'),
        ('UPI', 'UPI'),
        ('Card', 'Card'),
        ('Bank Transfer', 'Bank Transfer'),
        ('Cheque', 'Cheque'),
    ]

    fee_record = models.ForeignKey(
        FeeRecord,
        on_delete=models.PROTECT,
        related_name='payments'
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    payment_date = models.DateField()
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHODS
    )
    receipt_number = models.CharField(
        max_length=50,
        unique=True
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-payment_date', '-created_at']

    def __str__(self):
        return f'{self.receipt_number} - {self.amount}'


from django.conf import settings
from django.db import models


class AdminRegistrationRequest(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='admin_registration_request'
    )

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='Pending'
    )

    requested_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.status}"


class LowAttendanceAlert(models.Model):
    student = models.OneToOneField(
        Student,
        on_delete=models.CASCADE,
        related_name='low_attendance_alert'
    )

    alert_sent = models.BooleanField(default=False)
    attendance_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0
    )
    last_sent_at = models.DateTimeField(
        null=True,
        blank=True
    )

    def __str__(self):
        return f"Attendance alert - {self.student.student_id}"