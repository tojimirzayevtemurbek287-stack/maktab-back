from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class SchoolClass(models.Model):
    """Sinf, masalan: 10-A"""

    name = models.CharField(max_length=50, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Sinf"
        verbose_name_plural = "Sinflar"

    def __str__(self):
        return self.name


class User(AbstractUser):
    ROLE_CHOICES = (
        ("admin", "Administrator"),
        ("teacher", "O'qituvchi"),
        ("student", "O'quvchi"),
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="student")
    school_class = models.ForeignKey(
        SchoolClass,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="students",
    )
    # O'qituvchi o'zi ro'yxatdan o'tsa, administrator tasdiqlamaguncha False turadi
    is_approved = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        # createsuperuser bilan yaratilgan foydalanuvchi avtomatik administrator bo'ladi
        if self.is_superuser:
            self.role = "admin"
        super().save(*args, **kwargs)

    @property
    def display_name(self):
        return self.get_full_name() or self.username

    @property
    def is_teacher(self):
        return self.role == "teacher"

    @property
    def is_student(self):
        return self.role == "student"


class Assignment(models.Model):
    title = models.CharField(max_length=200)
    subject = models.CharField(max_length=100, blank=True)  # Fan: Matematika...
    description = models.TextField()
    school_class = models.ForeignKey(
        SchoolClass, on_delete=models.CASCADE, related_name="assignments"
    )
    teacher = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="assignments"
    )
    due_date = models.DateTimeField(null=True, blank=True)
    attachment = models.ImageField(upload_to="tasks/%Y/%m/", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.school_class})"

    @property
    def is_overdue(self):
        return bool(self.due_date and self.due_date < timezone.now())


class Submission(models.Model):
    """O'quvchining bitta vazifa bo'yicha topshirgan ishi"""

    assignment = models.ForeignKey(
        Assignment, on_delete=models.CASCADE, related_name="submissions"
    )
    student = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="submissions"
    )
    note = models.TextField(blank=True)
    grade = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    feedback = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    graded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["assignment", "student"], name="one_submission_per_student"
            )
        ]

    def __str__(self):
        return f"{self.student} → {self.assignment}"


class SubmissionImage(models.Model):
    submission = models.ForeignKey(
        Submission, on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(upload_to="submissions/%Y/%m/")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]


class Notification(models.Model):
    KIND_CHOICES = (
        ("new_assignment", "Yangi vazifa"),
        ("graded", "Baholandi"),
        ("submitted", "Topshirildi"),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    title = models.CharField(max_length=200)
    body = models.CharField(max_length=255, blank=True)
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
