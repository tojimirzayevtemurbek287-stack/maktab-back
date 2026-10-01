"""Sayt ichidagi administrator paneli uchun API (Django admin emas)."""
from django.contrib.auth import password_validation
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.db.models import Count, Q
from rest_framework import serializers, viewsets
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Assignment, SchoolClass, Submission, User


class IsAdmin(BasePermission):
    message = "Bu bo'lim faqat administratorlar uchun."

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and u.role == "admin")


# ---------- Sinflar ----------
class AdminClassSerializer(serializers.ModelSerializer):
    student_count = serializers.IntegerField(read_only=True)
    assignment_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = SchoolClass
        fields = ["id", "name", "student_count", "assignment_count"]

    def validate_name(self, value):
        value = value.strip()
        qs = SchoolClass.objects.filter(name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Bunday sinf allaqachon bor.")
        return value


class AdminClassViewSet(viewsets.ModelViewSet):
    serializer_class = AdminClassSerializer
    permission_classes = [IsAdmin]
    pagination_class = None

    def get_queryset(self):
        return SchoolClass.objects.annotate(
            student_count=Count("students", filter=Q(students__role="student"), distinct=True),
            assignment_count=Count("assignments", distinct=True),
        ).order_by("name")

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj.students.exists() or obj.assignments.exists():
            return Response(
                {"detail": "Bu sinfda o'quvchilar yoki vazifalar bor. Avval ularni boshqa sinfga o'tkazing."},
                status=400,
            )
        return super().destroy(request, *args, **kwargs)


# ---------- O'qituvchilar va o'quvchilar ----------
class AdminUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    full_name = serializers.CharField(source="display_name", read_only=True)
    school_class_name = serializers.CharField(source="school_class.name", read_only=True, default=None)

    class Meta:
        model = User
        fields = [
            "id", "username", "first_name", "last_name", "full_name",
            "role", "school_class", "school_class_name", "is_active", "is_approved",
            "password", "date_joined",
        ]
        read_only_fields = ["date_joined"]
        extra_kwargs = {"username": {"validators": [UnicodeUsernameValidator()]}}

    def validate_username(self, value):
        value = value.strip()
        qs = User.objects.filter(username__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Bu login band. Boshqa login tanlang.")
        return value

    def validate_role(self, value):
        if value not in ("teacher", "student"):
            raise serializers.ValidationError("Rol faqat o'qituvchi yoki o'quvchi bo'lishi mumkin.")
        return value

    def validate(self, attrs):
        role = attrs.get("role", getattr(self.instance, "role", "student"))
        school_class = attrs.get("school_class", getattr(self.instance, "school_class", None))
        password = attrs.get("password")

        if self.instance is None and not password:
            raise serializers.ValidationError({"password": "Parol kiriting."})
        if role == "student" and not school_class:
            raise serializers.ValidationError({"school_class": "O'quvchi uchun sinfni tanlang."})
        if role == "teacher":
            attrs["school_class"] = None
        if password:
            password_validation.validate_password(
                password, self.instance or User(username=attrs.get("username", ""))
            )
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class AdminUserViewSet(viewsets.ModelViewSet):
    serializer_class = AdminUserSerializer
    permission_classes = [IsAdmin]
    pagination_class = None

    def get_queryset(self):
        qs = (
            User.objects.exclude(role="admin")
            .exclude(is_superuser=True)
            .select_related("school_class")
            .order_by("last_name", "first_name", "username")
        )
        p = self.request.query_params
        if p.get("role") in ("teacher", "student"):
            qs = qs.filter(role=p["role"])
        if p.get("school_class"):
            qs = qs.filter(school_class_id=p["school_class"])
        search = (p.get("search") or "").strip()
        if search:
            qs = qs.filter(
                Q(username__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
            )
        return qs

    def destroy(self, request, *args, **kwargs):
        user = self.get_object()
        if user.role == "teacher" and user.assignments.exists():
            return Response(
                {"detail": "Bu o'qituvchining vazifalari bor. O'chirish o'rniga akkauntni faolsizlantiring."},
                status=400,
            )
        return super().destroy(request, *args, **kwargs)


# ---------- Umumiy statistika ----------
class AdminStatsView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        return Response(
            {
                "students": User.objects.filter(role="student", is_active=True).count(),
                "teachers": User.objects.filter(role="teacher", is_active=True).count(),
                "pending_teachers": User.objects.filter(role="teacher", is_approved=False).count(),
                "classes": SchoolClass.objects.count(),
                "assignments": Assignment.objects.count(),
                "submissions": Submission.objects.count(),
                "ungraded": Submission.objects.filter(grade__isnull=True).count(),
            }
        )
