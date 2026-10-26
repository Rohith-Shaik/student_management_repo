
from django import forms
from .models import Student, Course
from decimal import Decimal
from .models import Subject, Exam, Mark

class StudentForm(forms.ModelForm):
    course_ref = forms.ModelChoiceField(
        queryset=Course.objects.all(),
        empty_label="Select Course",
        required=True,
        widget=forms.Select(attrs={
            "class": "form-select"
        }),
        label="Course"
    )

    class Meta:
        model = Student
        fields = [
            'first_name',
            'last_name',
            'email',
            'phone',
            'gender',
            'course_ref',
            'date_of_birth',
            'address',
        ]

        widgets = {
            'date_of_birth': forms.DateInput(
                attrs={
                    'type': 'date',
                    'class': 'form-control'
                }
            ),
            'address': forms.Textarea(
                attrs={
                    'rows': 3,
                    'class': 'form-control'
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Show the current course when editing a student
        if self.instance and self.instance.pk and self.instance.course_ref:
            self.initial['course_ref'] = self.instance.course_ref

        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')

    def save(self, commit=True):
        student = super().save(commit=False)

        if student.course_ref:
            student.course = student.course_ref.course_name

        if commit:
            student.save()
            self.save_m2m()

        return student
class StudentProfileForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = [
            'first_name',
            'last_name',
            'email',
            'phone',
            'gender',
            'date_of_birth',
            'address',
        ]

        widgets = {
            'date_of_birth': forms.DateInput(
                attrs={
                    'type': 'date',
                    'class': 'form-control'
                }
            ),
            'address': forms.Textarea(
                attrs={
                    'rows': 3,
                    'class': 'form-control'
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            field.widget.attrs.setdefault(
                'class',
                'form-control'
            )

from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm


class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email'
        })
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['username'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Choose a username'
        })

        self.fields['password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Create a password'
        })

        self.fields['password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Confirm your password'
        })

from .models import Attendance


class AttendanceForm(forms.ModelForm):
    class Meta:
        model = Attendance
        fields = ['status', 'remarks']

        widgets = {
            'status': forms.Select(
                attrs={'class': 'form-select'}
            ),
            'remarks': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Optional remarks'
                }
            ),
        }



class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['course', 'subject_code', 'subject_name']

        widgets = {
            'course': forms.Select(attrs={'class': 'form-select'}),
            'subject_code': forms.TextInput(
                attrs={'class': 'form-control'}
            ),
            'subject_name': forms.TextInput(
                attrs={'class': 'form-control'}
            ),
        }


class ExamForm(forms.ModelForm):
    class Meta:
        model = Exam
        fields = [
            'subject',
            'exam_name',
            'exam_date',
            'max_marks',
            'pass_marks',
        ]
        widgets = {
            'subject': forms.Select(attrs={'class': 'form-select'}),
            'exam_name': forms.TextInput(
                attrs={'class': 'form-control'}
            ),
            'exam_date': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-control'}
            ),
            'max_marks': forms.NumberInput(
                attrs={
                    'class': 'form-control',
                    'min': '0.01',
                    'step': '0.01'
                }
            ),
            'pass_marks': forms.NumberInput(
                attrs={
                    'class': 'form-control',
                    'min': '0',
                    'step': '0.01'
                }
            ),
        }

    def clean(self):
        cleaned_data = super().clean()
        max_marks = cleaned_data.get('max_marks')
        pass_marks = cleaned_data.get('pass_marks')

        if (
            max_marks is not None
            and pass_marks is not None
            and pass_marks > max_marks
        ):
            self.add_error(
                'pass_marks',
                'Passing marks cannot exceed maximum marks.'
            )

        return cleaned_data


class MarkEntryForm(forms.Form):
    marks_obtained = forms.DecimalField(
        min_value=Decimal('0'),
        max_digits=7,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(
            attrs={
                'class': 'form-control',
                'min': '0',
                'step': '0.01',
                'placeholder': 'Marks'
            }
        )
    )

    remarks = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'Optional remarks'
            }
        )
    )



from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError

from .models import FeeRecord, FeePayment


class FeeRecordForm(forms.ModelForm):
    class Meta:
        model = FeeRecord
        fields = [
            'student',
            'fee_type',
            'academic_year',
            'total_amount',
            'due_date',
        ]
        widgets = {
            'student': forms.Select(attrs={
                'class': 'form-select',
            }),
            'fee_type': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Tuition Fee',
            }),
            'academic_year': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. 2026-2027',
            }),
            'total_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0.01',
                'step': '0.01',
            }),
            'due_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
            }),
        }

    def clean_total_amount(self):
        amount = self.cleaned_data['total_amount']

        if amount < Decimal('0.01'):
            raise ValidationError(
                'The fee amount must be greater than zero.'
            )

        return amount


class FeePaymentForm(forms.ModelForm):
    class Meta:
        model = FeePayment
        fields = [
            'amount',
            'payment_date',
            'payment_method',
            'receipt_number',
            'notes',
        ]
        widgets = {
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0.01',
                'step': '0.01',
            }),
            'payment_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
            }),
            'payment_method': forms.Select(attrs={
                'class': 'form-select',
            }),
            'receipt_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter a unique receipt number',
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Optional payment notes',
            }),
        }

    def __init__(self, *args, fee_record=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fee_record = fee_record

    def clean_amount(self):
        amount = self.cleaned_data['amount']

        if amount < Decimal('0.01'):
            raise ValidationError(
                'Payment amount must be greater than zero.'
            )

        if self.fee_record is not None:
            remaining = self.fee_record.balance

            if amount > remaining:
                raise ValidationError(
                    f'Payment exceeds the outstanding balance '
                    f'of {remaining:.2f}.'
                )

        return amount


from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm


class RegisterForm(UserCreationForm):
    first_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter first name'
        })
    )

    last_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter last name'
        })
    )

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter email address'
        })
    )

    class Meta:
        model = User
        fields = [
            'username',
            'first_name',
            'last_name',
            'email',
            'password1',
            'password2',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            field.widget.attrs.update({
                'class': 'form-control'
            })

    def clean_email(self):
        email = self.cleaned_data['email']

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                'An account with this email already exists.'
            )

        return email


from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm


class AdminRegisterForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter email address'
        })
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})

    def clean_email(self):
        email = self.cleaned_data['email']

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                'This email address is already registered.'
            )

        return email


from django.contrib.auth.forms import PasswordResetForm



from django.contrib.auth.forms import PasswordResetForm

class StudentPasswordResetForm(PasswordResetForm):
    """Allow password recovery for student accounts only."""

    def get_users(self, email):
        for user in super().get_users(email):
            if not user.is_staff and not user.is_superuser:
                yield user



class AdminPasswordResetForm(PasswordResetForm):
    """Allow password recovery for administrator accounts only."""

    def get_users(self, email):
        for user in super().get_users(email):
            if user.is_staff:
                yield user