from django import forms
from .models import RepairRequest


class RepairRequestForm(forms.ModelForm):
    image = forms.ImageField(required=False, label='Image attachment')

    def __init__(self, *args, language='th', location_locked=False, room_number='', **kwargs):
        super().__init__(*args, **kwargs)
        labels = {
            'th': {
                'title': 'หัวข้อปัญหา',
                'category': 'หมวดหมู่',
                'location': 'สถานที่ / ห้องพัก',
                'description': 'รายละเอียดปัญหา',
                'image': 'รูปภาพประกอบ (ไม่บังคับ)',
                'categories': {
                    '': 'เลือกหมวดหมู่',
                    RepairRequest.Category.ELECTRICITY: 'ไฟฟ้า',
                    RepairRequest.Category.PLUMBING: 'ประปา',
                    RepairRequest.Category.FURNITURE: 'เฟอร์นิเจอร์',
                    RepairRequest.Category.INTERNET: 'อินเทอร์เน็ต',
                    RepairRequest.Category.OTHER: 'อื่น ๆ',
                },
            },
            'en': {
                'title': 'Issue title',
                'category': 'Category',
                'location': 'Location / room',
                'description': 'Problem details',
                'image': 'Photo attachment (optional)',
                'categories': {
                    '': 'Choose a category',
                    RepairRequest.Category.ELECTRICITY: 'Electricity',
                    RepairRequest.Category.PLUMBING: 'Plumbing',
                    RepairRequest.Category.FURNITURE: 'Furniture',
                    RepairRequest.Category.INTERNET: 'Internet',
                    RepairRequest.Category.OTHER: 'Other',
                },
            },
        }
        localized_labels = labels.get(language, labels['th'])
        for field_name in ('title', 'category', 'location', 'description', 'image'):
            self.fields[field_name].label = localized_labels[field_name]
        self.fields['category'].choices = [
            (value, localized_labels['categories'][value])
            for value, _ in self.fields['category'].choices
        ]
        self.fields['category'].widget.attrs['class'] = 'repair-category-select'
        self.fields['image'].widget.attrs.update({
            'accept': 'image/*',
            'class': 'file-dropzone-input',
            'data-file-input': '',
        })
        if location_locked:
            self.fields['location'].disabled = True
            self.fields['location'].initial = room_number
            self.fields['location'].help_text = (
                'This is set from your account and cannot be changed here.'
                if language == 'en'
                else 'ระบบจะใช้เลขห้องที่บันทึกไว้ในบัญชีของคุณ และไม่สามารถแก้ไขได้ที่นี่'
            )
            self.fields['location'].error_messages['required'] = (
                'Your account has no room number. Please contact a supervisor before submitting.'
                if language == 'en'
                else 'บัญชีของคุณยังไม่มีเลขห้อง กรุณาติดต่อผู้ดูแลก่อนแจ้งซ่อม'
            )

    class Meta:
        model = RepairRequest
        fields = ('title', 'category', 'location', 'description', 'image')
        widgets = {'description': forms.Textarea(attrs={'rows': 5})}


class RepairUpdateForm(forms.ModelForm):
    def __init__(self, *args, language='th', **kwargs):
        super().__init__(*args, **kwargs)
        labels = {
            'th': {
                'status': {
                    RepairRequest.Status.RECEIVED: 'รับแจ้งแล้ว',
                    RepairRequest.Status.IN_PROGRESS: 'กำลังดำเนินการ',
                    RepairRequest.Status.WAITING: 'รออะไหล่',
                    RepairRequest.Status.COMPLETED: 'เสร็จสิ้น',
                    RepairRequest.Status.CANCELLED: 'ยกเลิก',
                },
                'supervisor_note': 'หมายเหตุจากผู้ดูแล',
                'assigned_to': 'ผู้รับผิดชอบ',
            },
            'en': {
                'status': {
                    RepairRequest.Status.RECEIVED: 'Received',
                    RepairRequest.Status.IN_PROGRESS: 'In progress',
                    RepairRequest.Status.WAITING: 'Waiting for parts',
                    RepairRequest.Status.COMPLETED: 'Completed',
                    RepairRequest.Status.CANCELLED: 'Cancelled',
                },
                'supervisor_note': 'Supervisor note',
                'assigned_to': 'Assigned to',
            },
        }
        localized_labels = labels.get(language, labels['th'])
        self.fields['status'].choices = [
            (value, localized_labels['status'][value])
            for value, _ in self.fields['status'].choices
        ]
        for field_name in ('supervisor_note', 'assigned_to'):
            self.fields[field_name].label = localized_labels[field_name]

    class Meta:
        model = RepairRequest
        fields = ('status', 'supervisor_note', 'assigned_to')
        widgets = {'supervisor_note': forms.Textarea(attrs={'rows': 4})}


class RepairCommentForm(forms.Form):
    def __init__(self, *args, language='th', **kwargs):
        super().__init__(*args, **kwargs)
        is_english = language == 'en'
        self.fields['body'] = forms.CharField(
            label='Comment' if is_english else 'ข้อความอัปเดต',
            max_length=2000,
            error_messages={
                'required': 'Enter an update.' if is_english else 'กรุณาเขียนข้อความอัปเดต',
                'max_length': 'Keep your update under 2,000 characters.' if is_english
                else 'ข้อความอัปเดตต้องไม่เกิน 2,000 ตัวอักษร',
            },
            widget=forms.Textarea(attrs={'rows': 3}),
        )
        self.fields['body'].widget.attrs.update({
            'placeholder': 'Share an update or ask a question...' if is_english
            else 'เขียนความคืบหน้าหรือคำถาม...',
            'maxlength': 2000,
        })


class RepairRatingForm(forms.Form):
    rating = forms.TypedChoiceField(
        choices=tuple((value, str(value)) for value in range(1, 6)),
        coerce=int,
        widget=forms.RadioSelect,
    )

    def __init__(self, *args, language='th', **kwargs):
        super().__init__(*args, **kwargs)
        is_english = language == 'en'
        self.fields['rating'].label = 'Your rating' if is_english else 'ให้คะแนนการซ่อม'
        self.fields['rating'].error_messages['required'] = (
            'Choose a star rating.' if is_english else 'กรุณาเลือกคะแนนดาว'
        )
        self.fields['rating'].error_messages['invalid_choice'] = (
            'Choose a rating from 1 to 5 stars.' if is_english else 'เลือกคะแนนตั้งแต่ 1 ถึง 5 ดาว'
        )
