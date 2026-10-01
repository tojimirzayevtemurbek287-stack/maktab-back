from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Assignment, Notification, SchoolClass, Submission, SubmissionImage, User


@admin.register(SchoolClass)
class SchoolClassAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "first_name", "last_name", "role", "school_class")
    list_filter = ("role", "school_class")
    fieldsets = UserAdmin.fieldsets + (("Maktab", {"fields": ("role", "school_class")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Maktab", {"fields": ("first_name", "last_name", "role", "school_class")}),
    )


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ("title", "school_class", "teacher", "due_date", "created_at")
    list_filter = ("school_class", "teacher")
    search_fields = ("title",)


class SubmissionImageInline(admin.TabularInline):
    model = SubmissionImage
    extra = 0


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ("assignment", "student", "grade", "submitted_at")
    list_filter = ("assignment__school_class",)
    inlines = [SubmissionImageInline]


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "kind", "is_read", "created_at")
    list_filter = ("kind", "is_read")
    search_fields = ("title", "body", "user__username")
