from django.conf import settings
from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import Assignment, Notification, SchoolClass, Submission, SubmissionImage, User


class SchoolClassSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchoolClass
        fields = ["id", "name"]


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="display_name", read_only=True)
    school_class_name = serializers.CharField(
        source="school_class.name", read_only=True, default=None
    )

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "full_name",
            "role",
            "school_class",
            "school_class_name",
        ]


class RegisterSerializer(serializers.ModelSerializer):
    """Faqat o'quvchilar ro'yxatdan o'tadi. O'qituvchilarni admin qo'shadi."""

    password = serializers.CharField(write_only=True)
    school_class = serializers.PrimaryKeyRelatedField(
        queryset=SchoolClass.objects.all(), required=True
    )
    first_name = serializers.CharField(required=True, max_length=150)
    last_name = serializers.CharField(required=True, max_length=150)

    class Meta:
        model = User
        fields = ["username", "password", "first_name", "last_name", "school_class"]

    def validate(self, attrs):
        user = User(**{k: v for k, v in attrs.items() if k != "password"})
        password_validation.validate_password(attrs["password"], user)
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data, role="student")
        user.set_password(password)
        user.save()
        return user


class SubmissionImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubmissionImage
        fields = ["id", "image"]


class SubmissionSerializer(serializers.ModelSerializer):
    images = SubmissionImageSerializer(many=True, read_only=True)
    student = serializers.SerializerMethodField()

    class Meta:
        model = Submission
        fields = [
            "id",
            "assignment",
            "student",
            "note",
            "grade",
            "feedback",
            "images",
            "submitted_at",
            "updated_at",
            "graded_at",
        ]

    def get_student(self, obj):
        return {"id": obj.student_id, "full_name": obj.student.display_name}


class GradeSerializer(serializers.Serializer):
    grade = serializers.IntegerField(min_value=1, max_value=5)
    feedback = serializers.CharField(required=False, allow_blank=True, default="")


class AssignmentSerializer(serializers.ModelSerializer):
    school_class = serializers.PrimaryKeyRelatedField(queryset=SchoolClass.objects.all())
    school_class_name = serializers.CharField(source="school_class.name", read_only=True)
    teacher_name = serializers.CharField(source="teacher.display_name", read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    # o'qituvchi uchun statistika (queryset annotatsiyasidan)
    total_students = serializers.IntegerField(read_only=True, required=False)
    submitted_count = serializers.IntegerField(read_only=True, required=False)
    graded_count = serializers.IntegerField(read_only=True, required=False)
    # o'quvchi uchun
    my_submission = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = Assignment
        fields = [
            "id",
            "title",
            "subject",
            "description",
            "school_class",
            "school_class_name",
            "teacher_name",
            "due_date",
            "attachment",
            "created_at",
            "is_overdue",
            "total_students",
            "submitted_count",
            "graded_count",
            "my_submission",
            "status",
        ]

    def _mine(self, obj):
        subs = getattr(obj, "my_submissions", None)
        return subs[0] if subs else None

    def get_my_submission(self, obj):
        request = self.context.get("request")
        if not request or request.user.role != "student":
            return None
        sub = self._mine(obj)
        return SubmissionSerializer(sub, context=self.context).data if sub else None

    def get_status(self, obj):
        request = self.context.get("request")
        if not request or request.user.role != "student":
            return None
        sub = self._mine(obj)
        if sub and sub.grade is not None:
            return "graded"
        if sub:
            return "submitted"
        return "overdue" if obj.is_overdue else "pending"


def validate_image_files(files):
    """Yuklangan rasmlar sonini va hajmini tekshiradi."""
    if not files:
        raise serializers.ValidationError("Kamida bitta rasm yuklang.")
    if len(files) > settings.MAX_IMAGES_PER_SUBMISSION:
        raise serializers.ValidationError(
            f"Bir vaqtda ko'pi bilan {settings.MAX_IMAGES_PER_SUBMISSION} ta rasm yuklash mumkin."
        )
    limit = settings.MAX_IMAGE_SIZE_MB * 1024 * 1024
    field = serializers.ImageField()  # Pillow bilan haqiqiy rasm ekanini tekshiradi
    for f in files:
        if f.size > limit:
            raise serializers.ValidationError(
                f"Rasm hajmi {settings.MAX_IMAGE_SIZE_MB} MB dan oshmasligi kerak."
            )
        try:
            field.run_validation(f)
        except DjangoValidationError:
            raise serializers.ValidationError(
                "Faqat rasm fayllarini (JPG, PNG, WEBP) yuklash mumkin."
            )
    return files


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "kind", "title", "body", "assignment", "is_read", "created_at"]
