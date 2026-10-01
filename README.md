# Maktab Vazifa — Backend (Django REST Framework)

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_demo      # ixtiyoriy: demo sinflar, ustoz va o'quvchi
python manage.py runserver
```

- `createsuperuser` bilan yaratilgan foydalanuvchi avtomatik **administrator** bo'ladi.
  Saytga (React) shu login bilan kirsangiz, sinflar, o'qituvchilar va o'quvchilarni boshqarish paneli ochiladi.
- Django admin (zaxira): http://127.0.0.1:8000/admin/
- O'quvchilar saytdan o'zlari ro'yxatdan o'tadi
- Testlar: `python manage.py test`

## Yangi: Xabarnomalar va parol almashtirish

`/api/notifications/` — o'quvchi/o'qituvchi/administrator o'ziga tegishli xabarnomalarni ko'radi (yangi vazifa, baholandi, topshirildi). `unread_count/`, `mark_read/`, `mark_all_read/` ham bor.
`/api/me/password/` — joriy foydalanuvchi o'z parolini almashtiradi.

## API

| Yo'l | Kim | Vazifasi |
|---|---|---|
| POST `/api/auth/login/` | hamma | kirish (token qaytaradi) |
| POST `/api/auth/register/` | hamma | o'quvchi ro'yxatdan o'tishi |
| GET `/api/me/` | kirgan | joriy foydalanuvchi |
| GET `/api/classes/` | hamma | sinflar ro'yxati |
| `/api/admin/stats/`, `/api/admin/classes/`, `/api/admin/users/?role=teacher\|student` | administrator | boshqaruv paneli |
| GET/POST `/api/assignments/` | ustoz yaratadi, o'quvchi o'z sinfinikini ko'radi | vazifalar |
| GET `/api/assignments/{id}/submissions/` | ustoz | topshirganlar va topshirmaganlar |
| POST `/api/assignments/{id}/submit/` | o'quvchi | rasmlar (`images`) + `note` bilan topshirish |
| POST `/api/submissions/{id}/grade/` | ustoz | `grade` (1-5) va `feedback` |

## Ishlab chiqarish (production) uchun

Muhit o'zgaruvchilari: `SECRET_KEY`, `DEBUG=False`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`.
