from rest_framework.permissions import BasePermission


class IsTeacher(BasePermission):
    message = "Bu amal faqat o'qituvchilar uchun."

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and u.role == "teacher")


class IsStudent(BasePermission):
    message = "Bu amal faqat o'quvchilar uchun."

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and u.role == "student")
