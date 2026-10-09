# โครงสร้างโปรเจกต์

DormFix แบ่งส่วนตามหน้าที่ของ Django: `accounts` ดูแลบัญชีผู้ใช้และแดชบอร์ด
ส่วน `repairs` ดูแลงานแจ้งซ่อมและ API เทมเพลตกับไฟล์หน้าจออยู่ที่ระดับโปรเจกต์
เพื่อให้ค้นหาและนำส่วนกลางกลับมาใช้ซ้ำได้ง่าย

## แผนผังโฟลเดอร์

```text
program/
├── accounts/                  # บัญชีผู้ใช้ การเข้าสู่ระบบ และแดชบอร์ด
│   ├── migrations/            # ประวัติฐานข้อมูลบัญชี รวม audit log ใน 0002
│   ├── admin.py               # การตั้งค่า Django Admin สำหรับผู้ใช้
│   ├── forms.py               # ฟอร์มสมัครสมาชิกและตั้งรหัสผ่าน
│   ├── models.py              # User model ที่โปรเจกต์กำหนดเอง
│   ├── tests.py               # การทดสอบบัญชี แดชบอร์ด และการเข้าสู่ระบบ
│   ├── urls.py                # เส้นทางหน้าบัญชีและแดชบอร์ด
│   └── views.py               # บัญชี แดชบอร์ด จัดการสมาชิก และรีเซ็ตรหัสผ่าน
├── dormrepair/                # การตั้งค่าหลักของ Django
│   ├── settings.py            # แอป middleware ฐานข้อมูล และอีเมล
│   ├── urls.py                # จุดรวมเส้นทางของโปรเจกต์
│   └── wsgi.py                # จุดเริ่มต้นสำหรับ WSGI
├── repairs/                   # งานซ่อม ความคิดเห็น คะแนน และการแจ้งเตือน
│   ├── migrations/            # ประวัติการเปลี่ยนฐานข้อมูลของงานซ่อม
│   ├── api_urls.py            # เส้นทาง API งานซ่อม
│   ├── api_views.py           # การทำงานของ API งานซ่อม
│   ├── forms.py               # ฟอร์มงานซ่อมและการตรวจสอบข้อมูล
│   ├── models.py              # RepairRequest, RepairComment, Notification
│   ├── notification_*.py      # API และ serializer ของการแจ้งเตือน
│   ├── notifications.py       # ฟังก์ชันสร้างการแจ้งเตือน
│   ├── serializers.py         # รูปแบบข้อมูลของ API งานซ่อม
│   ├── tests.py               # การทดสอบงานซ่อมและการแจ้งเตือน
│   └── views.py               # หน้างานซ่อม ความคิดเห็น และกล่องข้อความผู้ดูแล
├── templates/                  # เทมเพลต HTML ของ Django
│   ├── accounts/               # หน้าเข้าสู่ระบบ สมัครสมาชิก บัญชี และจัดการสมาชิก
│   │   └── management.html     # หน้าค้นหาและจัดการบัญชีสำหรับผู้ดูแล
│   ├── repairs/                # ฟอร์มแจ้งซ่อม หน้ารายละเอียด และความคิดเห็น
│   │   └── comment_management.html # กล่องบทสนทนาและตอบกลับสำหรับผู้ดูแล
│   ├── base.html               # โครงหน้าร่วมและเมนูนำทาง
│   └── dashboard.html          # แดชบอร์ดผู้พักอาศัยและผู้ดูแล
├── static/css/                 # ไฟล์รูปแบบหน้าจอ
├── docs/                       # คู่มือโปรเจกต์และการติดตั้ง
├── media/                      # ไฟล์อัปโหลดในเครื่อง; ไม่ควร commit
├── .vscode/                    # งานเสริมสำหรับ VS Code
├── manage.py                   # เครื่องมือสั่งงาน Django
├── requirements.txt            # แพ็กเกจ Python ที่โปรเจกต์ใช้
└── README.md                   # ภาพรวมและวิธีเริ่มต้นใช้งาน
```

ฐานข้อมูลในเครื่อง (`db.sqlite3`), ไฟล์อัปโหลด, virtual environment,
ไฟล์ static ที่สร้างขึ้น และ Python cache เป็นข้อมูล runtime หรือข้อมูลพัฒนา
ซึ่งยกเว้นจากระบบควบคุมเวอร์ชันด้วย `.gitignore`

## เริ่มแก้ไขจากไฟล์ไหน

| สิ่งที่ต้องการแก้ | ไฟล์ที่ควรเริ่มดู |
| --- | --- |
| ฟิลด์บัญชีหรือบทบาทผู้ใช้ | `accounts/models.py` |
| สมัครสมาชิกหรือฟอร์มรหัสผ่าน | `accounts/forms.py` |
| แดชบอร์ดสรุปสมาชิกและงานซ่อม | `accounts/views.py`, `templates/dashboard.html` |
| ค้นหา เปลี่ยนบทบาท หรือปิดใช้งานบัญชี | `accounts/views.py`, `templates/accounts/management.html` |
| ประวัติผู้ดำเนินการและการเปลี่ยนบัญชี | `accounts/models.py`, `templates/accounts/activity.html` |
| แถวบัญชีและปุ่มดำเนินการของผู้ดูแล | `templates/accounts/_account_management_row.html` |
| ฟิลด์งานซ่อม ความคิดเห็น หรือการแจ้งเตือน | `repairs/models.py` |
| ฟอร์มแจ้งซ่อมหรือการตรวจสอบข้อมูล | `repairs/forms.py` |
| ขั้นตอนทำงานหน้าเว็บงานซ่อม | `repairs/views.py` |
| ดูและตอบความคิดเห็นทุกคำขอ (ผู้ดูแล) | `repairs/views.py`, `templates/repairs/comment_management.html` |
| รูปแบบคำขอและคำตอบ API | `repairs/serializers.py`, `repairs/api_views.py` |
| API การแจ้งเตือน | `repairs/notification_api_views.py`, `repairs/notification_serializers.py` |
| เส้นทาง URL | `urls.py` ของแอป; เส้นทางหลักอยู่ใน `dormrepair/urls.py` |
| เนื้อหาหรือโครงหน้าเว็บ | เทมเพลตที่ตรงกับหน้านั้นใน `templates/` |
| รูปแบบหน้าจอ | `static/css/app.css` และ `static/css/theme.css` |
| การตั้งค่าโปรเจกต์หรืออีเมล | `dormrepair/settings.py` |

## ลำดับการทำงานหลัก

```text
เว็บเบราว์เซอร์
  └── dormrepair/urls.py
      ├── accounts/urls.py ── accounts/views.py ── accounts/forms.py
      └── repairs/urls.py  ── repairs/views.py  ── repairs/forms.py
                                  └── repairs/models.py

API
  └── dormrepair/urls.py ── repairs/api_urls.py ── repairs/api_views.py
                                                    └── repairs/serializers.py
```

เส้นทางหน้าเว็บส่งผลลัพธ์ผ่านเทมเพลต ส่วน API ตรวจสอบและจัดรูปแบบข้อมูลด้วย
Django REST Framework ทั้งสองส่วนใช้ repair models และฟังก์ชันแจ้งเตือนร่วมกัน
ตามความเหมาะสม

## ขั้นตอนเปลี่ยนโครงสร้างฐานข้อมูล

1. แก้ไข model ที่เกี่ยวข้อง
2. สร้าง migration ด้วย `python manage.py makemigrations`
3. ตรวจสอบไฟล์ที่สร้างในโฟลเดอร์ `migrations/` ของแอป
4. นำไปใช้ในเครื่องด้วย `python manage.py migrate`
5. รัน `python manage.py makemigrations --check --dry-run` และชุดทดสอบที่เกี่ยวข้อง

ไม่ควรแก้ migration ที่นำไปใช้แล้วเพื่อเปลี่ยนโครงสร้างฐานข้อมูล
ให้สร้าง migration ใหม่แทน
