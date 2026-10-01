from django.urls import path
from rest_framework.routers import DefaultRouter

from .admin_api import AdminClassViewSet, AdminStatsView, AdminUserViewSet
from .auth_views import LoginView, RegisterView
from .extra_api import MeStatsView, MyClassView
from .views import (
    AssignmentViewSet,
    ChangePasswordView,
    ClassListView,
    GradeSubmissionView,
    MeView,
    NotificationViewSet,
)

router = DefaultRouter()
router.register(r"assignments", AssignmentViewSet, basename="assignment")
router.register(r"notifications", NotificationViewSet, basename="notification")
router.register(r"admin/classes", AdminClassViewSet, basename="admin-class")
router.register(r"admin/users", AdminUserViewSet, basename="admin-user")

urlpatterns = [
    path("auth/login/", LoginView.as_view()),
    path("auth/register/", RegisterView.as_view()),
    path("me/", MeView.as_view()),
    path("me/password/", ChangePasswordView.as_view()),
    path("me/stats/", MeStatsView.as_view()),
    path("my-class/", MyClassView.as_view()),
    path("classes/", ClassListView.as_view()),
    path("submissions/<int:pk>/grade/", GradeSubmissionView.as_view()),
    path("admin/stats/", AdminStatsView.as_view()),
] + router.urls
