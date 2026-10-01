"""O'quvchi uchun qo'shimcha API: streak, yutuqlar, maqsad statistikasi va sinf sahifasi."""
from datetime import timedelta

from django.db.models import Avg, Count
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Assignment, Submission, User


def _streak(days):
    """Bugundan (yoki kecha) boshlab ketma-ket necha kun topshirilgani."""
    days = set(days)
    d = timezone.localdate()
    if d not in days:
        d -= timedelta(days=1)
    n = 0
    while d in days:
        n += 1
        d -= timedelta(days=1)
    return n


class MeStatsView(APIView):
    """GET /api/me/stats/ — streak, haftalik/oylik natija va yutuqlar."""

    def get(self, request):
        subs = Submission.objects.filter(student=request.user)
        days = [timezone.localtime(t).date() for t in subs.values_list("submitted_at", flat=True)]
        graded = subs.filter(grade__isnull=False)
        total, fives = subs.count(), graded.filter(grade=5).count()
        avg = graded.aggregate(a=Avg("grade"))["a"]
        streak = _streak(days)
        today = timezone.localdate()
        week_start = today - timedelta(days=today.weekday())
        week = sum(1 for d in days if d >= week_start)
        month = sum(1 for d in days if (d.year, d.month) == (today.year, today.month))

        def ach(key, title, hint, value, target):
            return {"key": key, "title": title, "hint": hint,
                    "value": min(value, target), "target": target, "done": value >= target}

        return Response({
            "streak": streak,
            "total_submitted": total,
            "graded": graded.count(),
            "average": round(avg, 1) if avg else None,
            "week": week,
            "month": month,
            "achievements": [
                ach("first", "Birinchi vazifa", "Birinchi vazifangizni topshiring", total, 1),
                ach("streak7", "7 kunlik streak", "7 kun ketma-ket vazifa topshiring", streak, 7),
                ach("ten", "10 ta topshiriq", "10 ta vazifa topshiring", total, 10),
                ach("fives", "A'lochi", "5 marta \"5\" baho oling", fives, 5),
                ach("active", "Faol o'quvchi", "20 ta vazifa topshiring", total, 20),
            ],
        })


class MyClassView(APIView):
    """GET /api/my-class/ — o'quvchining sinfi: o'quvchilar ro'yxati va statistika."""

    def get(self, request):
        cid = request.user.school_class_id
        if not cid:
            return Response({"name": None, "students": [], "students_count": 0,
                             "teachers_count": 0, "assignments_count": 0})
        students = (User.objects.filter(role="student", school_class_id=cid)
                    .annotate(done=Count("submissions")).order_by("last_name", "first_name"))
        assignments = Assignment.objects.filter(school_class_id=cid)
        return Response({
            "name": request.user.school_class.name,
            "students_count": students.count(),
            "teachers_count": assignments.values("teacher").distinct().count(),
            "assignments_count": assignments.count(),
            "students": [{"id": s.id, "full_name": s.display_name, "done": s.done} for s in students],
        })
