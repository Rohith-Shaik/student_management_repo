
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Course, Student, FeeRecord, FeePayment


User = get_user_model()


class FeeSecurityTests(TestCase):

    def setUp(self):
        # Create two independent student accounts.
        self.user_a = User.objects.create_user(
            username='student_a',
            password='TestPassword123!'
        )
        self.user_b = User.objects.create_user(
            username='student_b',
            password='TestPassword123!'
        )

        # Create a staff account.
        self.staff_user = User.objects.create_user(
            username='fee_admin',
            password='TestPassword123!',
            is_staff=True
        )

        # Create a course.
        self.course = Course.objects.create(
            course_code='BCA101',
            course_name='Bachelor of Computer Applications'
        )

        # Create student profiles.
        self.student_a = Student.objects.create(
            student_id='STU901',
            first_name='Student',
            last_name='Alpha',
            email='alpha@example.com',
            phone='9000000001',
            gender='Male',
            course=self.course.course_name,
            course_ref=self.course,
            date_of_birth=date(2005, 1, 1),
            user=self.user_a
        )

        self.student_b = Student.objects.create(
            student_id='STU902',
            first_name='Student',
            last_name='Beta',
            email='beta@example.com',
            phone='9000000002',
            gender='Female',
            course=self.course.course_name,
            course_ref=self.course,
            date_of_birth=date(2005, 2, 2),
            user=self.user_b
        )

        # Create one fee for each student.
        self.fee_a = FeeRecord.objects.create(
            student=self.student_a,
            fee_type='Tuition Fee',
            academic_year='2026-2027',
            total_amount=Decimal('10000.00')
        )

        self.fee_b = FeeRecord.objects.create(
            student=self.student_b,
            fee_type='Library Fee',
            academic_year='2026-2027',
            total_amount=Decimal('2000.00')
        )

        # Create a payment for Student A.
        self.payment_a = FeePayment.objects.create(
            fee_record=self.fee_a,
            amount=Decimal('2500.00'),
            payment_date=date(2026, 10, 1),
            payment_method='UPI',
            receipt_number='TEST-RECEIPT-901'
        )

    def test_student_sees_only_own_fee_balances(self):
        self.client.force_login(self.user_a)

        response = self.client.get(
            reverse('students:student_fee_balances')
        )

        self.assertEqual(response.status_code, 200)

        fee_ids = {
            fee.pk for fee in response.context['fees']
        }

        self.assertIn(self.fee_a.pk, fee_ids)
        self.assertNotIn(self.fee_b.pk, fee_ids)

    def test_student_sees_only_own_payment_history(self):
        # Give Student B a payment too.
        payment_b = FeePayment.objects.create(
            fee_record=self.fee_b,
            amount=Decimal('500.00'),
            payment_date=date(2026, 10, 2),
            payment_method='Cash',
            receipt_number='TEST-RECEIPT-902'
        )

        self.client.force_login(self.user_a)

        response = self.client.get(
            reverse('students:student_fee_payment_history')
        )

        self.assertEqual(response.status_code, 200)

        payment_ids = {
            payment.pk for payment in response.context['payments']
        }

        self.assertIn(self.payment_a.pk, payment_ids)
        self.assertNotIn(payment_b.pk, payment_ids)

    def test_student_cannot_access_fee_management(self):
        self.client.force_login(self.user_a)

        response = self.client.get(
            reverse('students:fee_list')
        )

        self.assertEqual(response.status_code, 302)

    def test_student_cannot_access_staff_receipt(self):
        self.client.force_login(self.user_a)

        response = self.client.get(
            reverse(
                'students:fee_receipt',
                kwargs={'payment_id': self.payment_a.pk}
            )
        )

        self.assertEqual(response.status_code, 302)

    def test_student_cannot_access_recycle_bin(self):
        self.client.force_login(self.user_a)

        response = self.client.get(
            reverse('students:fee_recycle_bin')
        )

        self.assertEqual(response.status_code, 302)

    def test_student_cannot_restore_deleted_fee(self):
        self.fee_a.is_deleted = True
        self.fee_a.save(
            update_fields=['is_deleted']
        )

        self.client.force_login(self.user_a)

        response = self.client.post(
            reverse(
                'students:restore_fee',
                kwargs={'fee_id': self.fee_a.pk}
            )
        )

        self.assertEqual(response.status_code, 302)

        self.fee_a.refresh_from_db()
        self.assertTrue(self.fee_a.is_deleted)

    def test_deleted_fee_is_hidden_from_student_balances(self):
        self.fee_a.is_deleted = True
        self.fee_a.save(
            update_fields=['is_deleted']
        )

        self.client.force_login(self.user_a)

        response = self.client.get(
            reverse('students:student_fee_balances')
        )

        self.assertEqual(response.status_code, 200)

        fee_ids = {
            fee.pk for fee in response.context['fees']
        }

        self.assertNotIn(self.fee_a.pk, fee_ids)

    def test_staff_can_restore_fee_and_preserve_payment(self):
        self.fee_a.is_deleted = True
        self.fee_a.save(
            update_fields=['is_deleted']
        )

        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse(
                'students:restore_fee',
                kwargs={'fee_id': self.fee_a.pk}
            )
        )

        self.assertEqual(response.status_code, 302)

        self.fee_a.refresh_from_db()

        self.assertFalse(self.fee_a.is_deleted)
        self.assertIsNone(self.fee_a.deleted_at)

        # The payment and receipt must still exist.
        self.assertTrue(
            FeePayment.objects.filter(
                pk=self.payment_a.pk,
                receipt_number='TEST-RECEIPT-901',
                fee_record=self.fee_a
            ).exists()
        )

    def test_student_cannot_record_fee_payment(self):
        self.client.force_login(self.user_a)

        response = self.client.get(
            reverse(
                'students:record_fee_payment',
                kwargs={'fee_id': self.fee_a.pk}
            )
        )

        self.assertEqual(response.status_code, 302)


class RegistrationSecurityTests(TestCase):

    def setUp(self):
        self.course = Course.objects.create(
            course_code='TEST101',
            course_name='Test Course'
        )

    def test_registration_page_is_accessible(self):
        response = self.client.get(
            reverse('students:register')
        )

        self.assertEqual(response.status_code, 200)

    def test_registration_creates_non_staff_user(self):
        response = self.client.post(
            reverse('students:register'),
            {
                'username': 'newstudent',
                'email': 'newstudent@example.com',
                'password1': 'SafeTestPass123!X',
                'password2': 'SafeTestPass123!X',
            }
        )

        self.assertEqual(response.status_code, 302)

        user = User.objects.get(username='newstudent')

        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_student_profile_is_linked_to_logged_in_user(self):
        user = User.objects.create_user(
            username='profile_student',
            password='SafeTestPass123!X'
        )

        self.client.force_login(user)

        response = self.client.post(
            reverse('students:complete_student_profile'),
            {
                'first_name': 'Profile',
                'last_name': 'Student',
                'email': 'profile_student@example.com',
                'phone': '9000000091',
                'gender': 'Male',
                'course_ref': self.course.pk,
                'date_of_birth': '2005-01-01',
                'address': 'Test Address',
            }
        )

        self.assertEqual(response.status_code, 302)

        student = Student.objects.get(user=user)

        self.assertEqual(student.user, user)
        self.assertEqual(student.course_ref, self.course)

    def test_existing_student_cannot_create_second_profile(self):
        user = User.objects.create_user(
            username='existing_student',
            password='SafeTestPass123!X'
        )

        Student.objects.create(
            student_id='STU991',
            first_name='Existing',
            last_name='Student',
            email='existing_student@example.com',
            phone='9000000092',
            gender='Male',
            course=self.course.course_name,
            course_ref=self.course,
            date_of_birth='2005-01-01',
            user=user
        )

        self.client.force_login(user)

        response = self.client.post(
            reverse('students:complete_student_profile'),
            {
                'first_name': 'Duplicate',
                'last_name': 'Profile',
                'email': 'duplicate@example.com',
                'phone': '9000000093',
                'gender': 'Female',
                'course_ref': self.course.pk,
                'date_of_birth': '2005-02-02',
                'address': 'Another Address',
            }
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            Student.objects.filter(user=user).count(),
            1
        )

    def test_student_can_choose_course(self):
        user = User.objects.create_user(
            username='course_student',
            password='SafeTestPass123!X'
        )

        self.client.force_login(user)

        response = self.client.post(
            reverse('students:complete_student_profile'),
            {
                'first_name': 'Course',
                'last_name': 'Student',
                'email': 'course_student@example.com',
                'phone': '9000000094',
                'gender': 'Female',
                'course_ref': self.course.pk,
                'date_of_birth': '2005-03-03',
                'address': 'Course Test Address',
            }
        )

        self.assertEqual(response.status_code, 302)

        student = Student.objects.get(user=user)

        self.assertEqual(student.course_ref, self.course)
        self.assertEqual(student.course, self.course.course_name)



from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from students.forms import FeePaymentForm
from students.models import Course, Student, FeeRecord, FeePayment


class PaymentValidationTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.staff_user = User.objects.create_user(
            username='payment_test_admin',
            password='TestPassword123!',
            is_staff=True,
        )

        cls.course = Course.objects.create(
            course_code='PAY101',
            course_name='Payment Testing Course',
        )

        cls.student = Student.objects.create(
            student_id='PAY901',
            first_name='Test',
            last_name='Student',
            email='paytest@example.com',
            phone='9876501234',
            gender='Male',
            course='Payment Testing Course',
            course_ref=cls.course,
            date_of_birth=date(2002, 1, 15),
        )

        cls.fee = FeeRecord.objects.create(
            student=cls.student,
            fee_type='Tuition Fee',
            academic_year='2026-2027',
            total_amount=Decimal('10000.00'),
        )

        # Existing payment leaves ₹7,500 outstanding.
        FeePayment.objects.create(
            fee_record=cls.fee,
            amount=Decimal('2500.00'),
            payment_date=date(2026, 10, 1),
            payment_method='UPI',
            receipt_number='PAY-TEST-001',
        )

    def payment_data(self, amount, receipt='PAY-TEST-002'):
        return {
            'amount': str(amount),
            'payment_date': '2026-10-22',
            'payment_method': 'UPI',
            'receipt_number': receipt,
            'notes': 'Automated validation test',
        }

    def test_payment_within_balance_is_valid(self):
        form = FeePaymentForm(
            data=self.payment_data('5000.00'),
            fee_record=self.fee,
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_payment_equal_to_remaining_balance_is_valid(self):
        form = FeePaymentForm(
            data=self.payment_data('7500.00'),
            fee_record=self.fee,
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_payment_exceeding_balance_is_rejected(self):
        form = FeePaymentForm(
            data=self.payment_data('7500.01'),
            fee_record=self.fee,
        )

        self.assertFalse(form.is_valid())
        self.assertIn('amount', form.errors)
        self.assertIn(
            'Payment exceeds the outstanding balance',
            str(form.errors['amount']),
        )

    def test_zero_payment_is_rejected(self):
        form = FeePaymentForm(
            data=self.payment_data('0.00'),
            fee_record=self.fee,
        )

        self.assertFalse(form.is_valid())
        self.assertIn('amount', form.errors)

    def test_negative_payment_is_rejected(self):
        form = FeePaymentForm(
            data=self.payment_data('-10.00'),
            fee_record=self.fee,
        )

        self.assertFalse(form.is_valid())
        self.assertIn('amount', form.errors)

    def test_duplicate_receipt_number_is_rejected(self):
        form = FeePaymentForm(
            data=self.payment_data(
                '100.00',
                receipt='PAY-TEST-001',
            ),
            fee_record=self.fee,
        )

        self.assertFalse(form.is_valid())
        self.assertIn('receipt_number', form.errors)

    def test_deleted_fee_cannot_receive_payment(self):
        self.fee.is_deleted = True
        self.fee.save(update_fields=['is_deleted'])

        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse(
                'students:record_fee_payment',
                args=[self.fee.pk],
            ),
            data=self.payment_data('100.00'),
        )

        self.assertEqual(response.status_code, 404)

        # No additional payment should have been created.
        self.assertEqual(
            FeePayment.objects.filter(fee_record=self.fee).count(),
            1,
        )

    def test_valid_payment_is_saved_through_view(self):
        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse(
                'students:record_fee_payment',
                args=[self.fee.pk],
            ),
            data=self.payment_data(
                '1000.00',
                receipt='PAY-TEST-003',
            ),
        )

        self.assertEqual(response.status_code, 302)

        self.assertTrue(
            FeePayment.objects.filter(
                fee_record=self.fee,
                amount=Decimal('1000.00'),
                receipt_number='PAY-TEST-003',
            ).exists()
        )

    def test_overpayment_is_not_saved_through_view(self):
        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse(
                'students:record_fee_payment',
                args=[self.fee.pk],
            ),
            data=self.payment_data(
                '8000.00',
                receipt='PAY-TEST-004',
            ),
        )

        self.assertEqual(response.status_code, 200)

        self.assertFalse(
            FeePayment.objects.filter(
                receipt_number='PAY-TEST-004',
            ).exists()
        )
