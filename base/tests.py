import io
import shutil
import tempfile

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.test import APITestCase

from .models import Assignment, Notification, SchoolClass, User

TMP_MEDIA = tempfile.mkdtemp()


def make_image(name="hw.jpg"):
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), "white").save(buf, "JPEG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/jpeg")


@override_settings(MEDIA_ROOT=TMP_MEDIA)
class HomeworkFlowTests(APITestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP_MEDIA, ignore_errors=True)

    def setUp(self):
        cache.clear()  # login cheklovi testlarga xalaqit bermasin
        self.cls = SchoolClass.objects.create(name="10-A")
        self.other_cls = SchoolClass.objects.create(name="9-B")
        self.teacher = User.objects.create_user("teach", password="secret12", role="teacher", first_name="Aziza", last_name="Karimova")
        self.student = User.objects.create_user("stud", password="secret12", role="student", school_class=self.cls, first_name="Ali", last_name="Valiyev")
        self.student2 = User.objects.create_user("stud2", password="secret12", role="student", school_class=self.cls, first_name="Vali", last_name="Aliyev")
        self.outsider = User.objects.create_user("out", password="secret12", role="student", school_class=self.other_cls)

    def login(self, username):
        r = self.client.post("/api/auth/login/", {"username": username, "password": "secret12"})
        self.assertEqual(r.status_code, 200, r.content)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {r.data['token']}")

    def test_register_student(self):
        r = self.client.post("/api/auth/register/", {
            "username": "new", "password": "abcdef1", "first_name": "N", "last_name": "S",
            "school_class": self.cls.id,
        })
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data["user"]["role"], "student")

    def test_wrong_login(self):
        r = self.client.post("/api/auth/login/", {"username": "stud", "password": "bad"})
        self.assertEqual(r.status_code, 400)

    def test_full_flow(self):
        # o'qituvchi vazifa yaratadi
        self.login("teach")
        r = self.client.post("/api/assignments/", {
            "title": "Masalalar", "subject": "Matematika", "description": "5-mashq",
            "school_class": self.cls.id,
        })
        self.assertEqual(r.status_code, 201, r.content)
        aid = r.data["id"]

        # o'quvchi ko'radi
        self.login("stud")
        r = self.client.get("/api/assignments/")
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["status"], "pending")
        # boshqa sinf o'quvchisi ko'rmaydi
        self.login("out")
        self.assertEqual(len(self.client.get("/api/assignments/").data), 0)
        # o'quvchi vazifa yarata olmaydi
        self.login("stud")
        r = self.client.post("/api/assignments/", {"title": "x", "description": "y", "school_class": self.cls.id})
        self.assertEqual(r.status_code, 403)

        # rasmsiz topshirish rad etiladi
        r = self.client.post(f"/api/assignments/{aid}/submit/", {"note": "hi"}, format="multipart")
        self.assertEqual(r.status_code, 400)
        # rasm bilan topshirish
        r = self.client.post(f"/api/assignments/{aid}/submit/", {"note": "tayyor", "images": [make_image(), make_image("b.jpg")]}, format="multipart")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(len(r.data["images"]), 2)
        # qayta topshirish (rasmlar almashadi)
        r = self.client.post(f"/api/assignments/{aid}/submit/", {"images": [make_image()]}, format="multipart")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data["images"]), 1)
        sub_id = r.data["id"]
        self.assertEqual(self.client.get("/api/assignments/").data[0]["status"], "submitted")
        # soxta fayl rad etiladi
        self.login("stud2")
        bad = SimpleUploadedFile("x.jpg", b"not an image", content_type="image/jpeg")
        r = self.client.post(f"/api/assignments/{aid}/submit/", {"images": [bad]}, format="multipart")
        self.assertEqual(r.status_code, 400)

        # o'qituvchi natijalarni ko'radi
        self.login("teach")
        r = self.client.get("/api/assignments/")
        self.assertEqual(r.data[0]["total_students"], 2)
        self.assertEqual(r.data[0]["submitted_count"], 1)
        r = self.client.get(f"/api/assignments/{aid}/submissions/")
        self.assertEqual(len(r.data["submissions"]), 1)
        self.assertEqual([m["full_name"] for m in r.data["missing"]], ["Vali Aliyev"])
        # baholash
        r = self.client.post(f"/api/submissions/{sub_id}/grade/", {"grade": 5, "feedback": "Barakalla"})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self.client.post(f"/api/submissions/{sub_id}/grade/", {"grade": 9}).status_code, 400)
        self.assertEqual(self.client.get("/api/assignments/").data[0]["graded_count"], 1)

        # o'quvchi bahoni ko'radi va qayta topshira olmaydi
        self.login("stud")
        item = self.client.get("/api/assignments/").data[0]
        self.assertEqual(item["status"], "graded")
        self.assertEqual(item["my_submission"]["grade"], 5)
        r = self.client.post(f"/api/assignments/{aid}/submit/", {"images": [make_image()]}, format="multipart")
        self.assertEqual(r.status_code, 400)

    def test_teacher_cannot_grade_others(self):
        t2 = User.objects.create_user("t2", password="secret12", role="teacher")
        a = Assignment.objects.create(title="a", description="d", school_class=self.cls, teacher=self.teacher)
        from .models import Submission
        s = Submission.objects.create(assignment=a, student=self.student)
        self.login("t2")
        r = self.client.post(f"/api/submissions/{s.id}/grade/", {"grade": 3})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.client.get(f"/api/assignments/{a.id}/").status_code, 404)


class NotificationTests(APITestCase):
    def setUp(self):
        self.cls = SchoolClass.objects.create(name="10-A")
        self.teacher = User.objects.create_user("teach", password="secret12", role="teacher")
        self.student = User.objects.create_user("stud", password="secret12", role="student", school_class=self.cls)

    def login(self, u):
        r = self.client.post("/api/auth/login/", {"username": u, "password": "secret12"})
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {r.data['token']}")

    def test_notification_flow(self):
        self.login("teach")
        r = self.client.post("/api/assignments/", {"title": "Uy ishi", "description": "d", "school_class": self.cls.id})
        aid = r.data["id"]

        self.login("stud")
        self.assertEqual(self.client.get("/api/notifications/unread_count/").data["count"], 1)
        notes = self.client.get("/api/notifications/").data
        self.assertEqual(notes[0]["kind"], "new_assignment")
        nid = notes[0]["id"]
        self.client.post(f"/api/notifications/{nid}/mark_read/")
        self.assertEqual(self.client.get("/api/notifications/unread_count/").data["count"], 0)

        self.client.post(f"/api/assignments/{aid}/submit/", {"images": [make_image()]}, format="multipart")

        self.login("teach")
        self.assertEqual(self.client.get("/api/notifications/unread_count/").data["count"], 1)
        self.client.post("/api/notifications/mark_all_read/")
        self.assertEqual(self.client.get("/api/notifications/unread_count/").data["count"], 0)
        sub_id = self.client.get(f"/api/assignments/{aid}/submissions/").data["submissions"][0]["id"]
        self.client.post(f"/api/submissions/{sub_id}/grade/", {"grade": 5, "feedback": "zo'r"})

        self.login("stud")
        self.assertEqual(self.client.get("/api/notifications/unread_count/").data["count"], 1)
        notes = self.client.get("/api/notifications/").data
        self.assertEqual(notes[0]["kind"], "graded")

    def test_cannot_see_others_notifications(self):
        other = User.objects.create_user("stud2", password="secret12", role="student", school_class=self.cls)
        Notification.objects.create(user=other, kind="graded", title="x")
        self.login("stud")
        self.assertEqual(len(self.client.get("/api/notifications/").data), 0)


class ChangePasswordTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user("u1", password="secret12", role="teacher")

    def test_change_password(self):
        r = self.client.post("/api/auth/login/", {"username": "u1", "password": "secret12"})
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {r.data['token']}")
        bad = self.client.post("/api/me/password/", {"old_password": "wrong", "new_password": "newpass1"})
        self.assertEqual(bad.status_code, 400)
        ok = self.client.post("/api/me/password/", {"old_password": "secret12", "new_password": "newpass1"})
        self.assertEqual(ok.status_code, 200, ok.content)
        self.client.credentials()
        self.assertEqual(self.client.post("/api/auth/login/", {"username": "u1", "password": "newpass1"}).status_code, 200)
