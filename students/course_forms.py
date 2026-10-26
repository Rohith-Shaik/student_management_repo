
from django import forms
from .models import Course


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = [
            'course_code',
            'course_name',
            'description',
        ]
        widgets = {
            'description': forms.Textarea(
                attrs={'rows': 3}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            field.widget.attrs.update({
                'class': 'form-control'
            })
