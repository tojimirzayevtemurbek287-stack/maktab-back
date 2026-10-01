from django.core.cache import cache
from rest_framework.test import APITestCase

from .models import Assignment, SchoolClass, User


class AdminPanelTests(APITestCase):
    def setUp(self):
        cache.clear()  # login cheklovi testlarga xalaqit bermasin
        self.client.default_format = "json"
        self.admin = User.objects.create_superuser("boss", password="secret12")
        self.teacher = User.objects.create_user("t", password="secret12", role="teacher")
        self.cls = SchoolClass.objects.create(name="10-A")

    def login(self, u):
        r = self.client.post("/api/auth/login/", {"username": u, "password": "secret12"})
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {r.data['token']}")
        return r.data

    def test_superuser_gets_admin_role(self):
        self.assertEqual(self.login("boss")["user"]["role"], "admin")

    def test_non_admin_forbidden(self):
        self.login("t")
        for url in ("/api/admin/stats/", "/api/admin/classes/", "/api/admin/users/"):
            self.assertEqual(self.client.get(url).status_code, 403)

    def test_classes_crud_and_guard(self):
        self.login("boss")
        r = self.client.post("/api/admin/classes/", {"name": " 9-B "})
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(self.client.post("/api/admin/classes/", {"name": "9-b"}).status_code, 400)
        cid = r.data["id"]
        self.assertEqual(self.client.patch(f"/api/admin/classes/{cid}/", {"name": "9-V"}).status_code, 200)
        self.assertEqual(self.client.delete(f"/api/admin/classes/{cid}/").status_code, 204)
        User.objects.create_user("s", password="x", role="student", school_class=self.cls)
        self.assertEqual(self.client.delete(f"/api/admin/classes/{self.cls.id}/").status_code, 400)
        lst = self.client.get("/api/admin/classes/").data
        self.assertEqual(lst[0]["student_count"], 1)

    def test_users_flow(self):
        self.login("boss")
        # o'qituvchi yaratish
        r = self.client.post("/api/admin/users/", {"username": "ustoz1", "password": "abcdef1", "first_name": "A", "last_name": "B", "role": "teacher"})
        self.assertEqual(r.status_code, 201, r.content)
        self.assertNotIn("password", r.data)
        # o'quvchi sinfsiz bo'lmaydi
        r2 = self.client.post("/api/admin/users/", {"username": "st1", "password": "abcdef1", "role": "student"})
        self.assertEqual(r2.status_code, 400)
        r2 = self.client.post("/api/admin/users/", {"username": "st1", "password": "abcdef1", "first_name": "S", "last_name": "T", "role": "student", "school_class": self.cls.id})
        self.assertEqual(r2.status_code, 201, r2.content)
        # login band
        self.assertEqual(self.client.post("/api/admin/users/", {"username": "ST1", "password": "abcdef1", "role": "teacher"}).status_code, 400)
        # admin rolini berib bo'lmaydi
        self.assertEqual(self.client.post("/api/admin/users/", {"username": "x", "password": "abcdef1", "role": "admin"}).status_code, 400)
        # filtr va qidiruv
        self.assertEqual(len(self.client.get("/api/admin/users/?role=student").data), 1)
        self.assertEqual(len(self.client.get("/api/admin/users/?search=ustoz").data), 1)
        # adminning o'zi ro'yxatda ko'rinmaydi
        self.assertFalse(any(u["username"] == "boss" for u in self.client.get("/api/admin/users/").data))
        # tahrirlash + parol almashtirish + faolsizlantirish
        uid = r2.data["id"]
        r3 = self.client.patch(f"/api/admin/users/{uid}/", {"password": "newpass99", "is_active": False})
        self.assertEqual(r3.status_code, 200, r3.content)
        self.client.credentials()
        bad = self.client.post("/api/auth/login/", {"username": "st1", "password": "newpass99"})
        self.assertEqual(bad.status_code, 400)  # faolsiz akkaunt kira olmaydi
        self.login("boss")
        self.client.patch(f"/api/admin/users/{uid}/", {"is_active": True})
        self.client.credentials()
        self.assertEqual(self.client.post("/api/auth/login/", {"username": "st1", "password": "newpass99"}).status_code, 200)
        self.login("boss")
        # vazifasi bor o'qituvchini o'chirib bo'lmaydi
        Assignment.objects.create(title="a", description="d", school_class=self.cls, teacher=self.teacher)
        self.assertEqual(self.client.delete(f"/api/admin/users/{self.teacher.id}/").status_code, 400)
        self.assertEqual(self.client.delete(f"/api/admin/users/{uid}/").status_code, 204)

    def test_stats(self):
        self.login("boss")
        self.assertEqual(self.client.get("/api/admin/stats/").data["classes"], 1)


class SignUpTests(APITestCase):
    def setUp(self):
        cache.clear()  # login cheklovi testlarga xalaqit bermasin
        self.client.default_format = "json"
        self.admin = User.objects.create_superuser("boss", password="secret12")
        self.cls = SchoolClass.objects.create(name="10-A")

    def test_student_signup_returns_token(self):
        r = self.client.post("/api/auth/register/", {"username": "s1", "password": "abcdef1", "first_name": "A", "last_name": "B", "role": "student", "school_class": self.cls.id})
        self.assertEqual(r.status_code, 201, r.content)
        self.assertIn("token", r.data)
        self.assertEqual(r.data["user"]["role"], "student")

    def test_student_needs_class(self):
        r = self.client.post("/api/auth/register/", {"username": "s1", "password": "abcdef1", "first_name": "A", "last_name": "B", "role": "student"})
        self.assertEqual(r.status_code, 400)

    def test_teacher_pending_until_approved(self):
        r = self.client.post("/api/auth/register/", {"username": "t1", "password": "abcdef1", "first_name": "T", "last_name": "U", "role": "teacher"})
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(r.data["pending"])
        self.assertNotIn("token", r.data)
        # kira olmaydi
        bad = self.client.post("/api/auth/login/", {"username": "t1", "password": "abcdef1"})
        self.assertEqual(bad.status_code, 403)
        # admin tasdiqlaydi
        lg = self.client.post("/api/auth/login/", {"username": "boss", "password": "secret12"})
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {lg.data['token']}")
        self.assertEqual(self.client.get("/api/admin/stats/").data["pending_teachers"], 1)
        uid = User.objects.get(username="t1").id
        self.assertEqual(self.client.patch(f"/api/admin/users/{uid}/", {"is_approved": True}).status_code, 200)
        self.client.credentials()
        ok = self.client.post("/api/auth/login/", {"username": "t1", "password": "abcdef1"})
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.data["user"]["role"], "teacher")

    def test_cannot_signup_as_admin(self):
        r = self.client.post("/api/auth/register/", {"username": "x", "password": "abcdef1", "first_name": "A", "last_name": "B", "role": "admin"})
        self.assertEqual(r.status_code, 400)

    def test_duplicate_username(self):
        r = self.client.post("/api/auth/register/", {"username": "BOSS", "password": "abcdef1", "first_name": "A", "last_name": "B", "role": "teacher"})
        self.assertEqual(r.status_code, 400)
