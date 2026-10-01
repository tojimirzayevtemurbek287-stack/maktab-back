from django.contrib.auth import authenticate, password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Count, IntegerField, OuterRef, Prefetch, Q, Subquery
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import GenericAPIView, ListAPIView, RetrieveAPIView
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.decorators import action as _action  # noqa (kept for clarity)
from rest_framework.views import APIView



from .models import Assignment, Notification, SchoolClass, Submission, SubmissionImage, User
from .permissions import IsStudent, IsTeacher
from .serializers import (
    AssignmentSerializer,
    GradeSerializer,
    NotificationSerializer,
    RegisterSerializer,
    SchoolClassSerializer,
    SubmissionSerializer,
    UserSerializer,
    validate_image_files,
)


class AuthThrottle(AnonRateThrottle):
    scope = "auth"


def auth_response(user):
    token, _ = Token.objects.get_or_create(user=user)
    return {"token": token.key, "user": UserSerializer(user).data}


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthThrottle]

    def post(self, request):
        user = authenticate(
            username=(request.data.get("username") or "").strip(),
            password=request.data.get("password") or "",
        )
        if not user:
            return Response(
                {"detail": "Login yoki parol noto'g'ri."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(auth_response(user))


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthThrottle]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(auth_response(user), status=status.HTTP_201_CREATED)


class MeView(RetrieveAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class ChangePasswordView(APIView):
    def post(self, request):
        user = request.user
        old_password = request.data.get("old_password") or ""
        new_password = request.data.get("new_password") or ""
        if not user.check_password(old_password):
            return Response({"detail": "Joriy parol noto'g'ri."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            password_validation.validate_password(new_password, user)
        except DjangoValidationError as exc:
            return Response({"detail": " ".join(exc.messages)}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(new_password)
        user.save()
        return Response({"ok": True})


class ClassListView(ListAPIView):
    """Ro'yxatdan o'tish oynasida sinf tanlash uchun ochiq ro'yxat."""

    permission_classes = [permissions.AllowAny]
    serializer_class = SchoolClassSerializer
    queryset = SchoolClass.objects.all()
    pagination_class = None


class AssignmentViewSet(viewsets.ModelViewSet):
    serializer_class = AssignmentSerializer

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy", "submissions"):
            return [IsTeacher()]
        if self.action == "submit":
            return [IsStudent()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        qs = Assignment.objects.select_related("school_class", "teacher")
        if user.role == "teacher":
            students = (
                User.objects.filter(role="student", school_class=OuterRef("school_class"))
                .values("school_class")
                .annotate(c=Count("id"))
                .values("c")
            )
            return (
                qs.filter(teacher=user)
                .annotate(
                    total_students=Coalesce(
                        Subquery(students, output_field=IntegerField()), 0
                    ),
                    submitted_count=Count("submissions", distinct=True),
                    graded_count=Count(
                        "submissions",
                        filter=Q(submissions__grade__isnull=False),
                        distinct=True,
                    ),
                )
                .order_by("-created_at")
            )
        if not user.school_class_id:
            return qs.none()
        mine = Submission.objects.filter(student=user).prefetch_related("images")
        return qs.filter(school_class_id=user.school_class_id).prefetch_related(
            Prefetch("submissions", queryset=mine, to_attr="my_submissions")
        )

    def perform_create(self, serializer):
        assignment = serializer.save(teacher=self.request.user)
        students = User.objects.filter(role="student", school_class=assignment.school_class)
        Notification.objects.bulk_create([
            Notification(
                user=s, kind="new_assignment",
                title="Yangi vazifa",
                body=f"{assignment.subject or 'Vazifa'}: {assignment.title}",
                assignment=assignment,
            )
            for s in students
        ])

    @action(detail=True, methods=["get"])
    def submissions(self, request, pk=None):
        """O'qituvchi: topshirganlar va topshirmaganlar ro'yxati."""
        assignment = self.get_object()
        subs = assignment.submissions.select_related("student").prefetch_related("images")
        submitted_ids = [s.student_id for s in subs]
        missing = User.objects.filter(
            role="student", school_class=assignment.school_class
        ).exclude(id__in=submitted_ids)
        return Response(
            {
                "submissions": SubmissionSerializer(
                    subs, many=True, context={"request": request}
                ).data,
                "missing": [
                    {"id": u.id, "full_name": u.display_name} for u in missing
                ],
            }
        )

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        """O'quvchi: rasmlar bilan vazifani topshirish (qayta topshirish ham mumkin)."""
        assignment = self.get_object()
        files = request.FILES.getlist("images")
        validate_image_files(files)

        with transaction.atomic():
            sub, created = Submission.objects.select_for_update().get_or_create(
                assignment=assignment, student=request.user
            )
            if sub.grade is not None:
                return Response(
                    {"detail": "Bu ish baholangan, uni qayta topshirib bo'lmaydi."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            sub.note = request.data.get("note", "")[:2000]
            sub.save()
            if not created:
                sub.images.all().delete()
            for f in files:
                SubmissionImage.objects.create(submission=sub, image=f)

        sub = Submission.objects.prefetch_related("images").get(pk=sub.pk)
        Notification.objects.create(
            user=assignment.teacher, kind="submitted",
            title="Yangi ish topshirildi",
            body=f"{request.user.display_name}: {assignment.title}",
            assignment=assignment,
        )
        return Response(
            SubmissionSerializer(sub, context={"request": request}).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class GradeSubmissionView(GenericAPIView):
    permission_classes = [IsTeacher]
    serializer_class = GradeSerializer

    def post(self, request, pk):
        try:
            sub = Submission.objects.select_related("assignment", "student").get(pk=pk)
        except Submission.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if sub.assignment.teacher_id != request.user.id:
            raise PermissionDenied("Bu boshqa o'qituvchining vazifasi.")
        s = GradeSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        sub.grade = s.validated_data["grade"]
        sub.feedback = s.validated_data["feedback"]
        sub.graded_at = timezone.now()
        sub.save()
        Notification.objects.create(
            user=sub.student, kind="graded",
            title="Ishingiz baholandi",
            body=f"{sub.assignment.title}: {sub.grade} baho",
            assignment=sub.assignment,
        )
        sub = Submission.objects.prefetch_related("images").get(pk=sub.pk)
        return Response(SubmissionSerializer(sub, context={"request": request}).data)


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

    @action(detail=False, methods=["get"])
    def unread_count(self, request):
        return Response({"count": self.get_queryset().filter(is_read=False).count()})

    @action(detail=False, methods=["post"])
    def mark_all_read(self, request):
        self.get_queryset().filter(is_read=False).update(is_read=True)
        return Response({"ok": True})

    @action(detail=True, methods=["post"])
    def mark_read(self, request, pk=None):
        n = self.get_object()
        n.is_read = True
        n.save(update_fields=["is_read"])
        return Response(NotificationSerializer(n).data)
