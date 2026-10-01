from django.core.management.base import BaseCommand

from base.models import SchoolClass, User


class Command(BaseCommand):
    help = "Sinovdan o'tkazish uchun demo sinflar, o'qituvchi va o'quvchi yaratadi"

    def handle(self, *args, **options):
        classes = [SchoolClass.objects.get_or_create(name=n)[0] for n in ("9-A", "9-B", "10-A", "10-B", "11-A")]
        if not User.objects.filter(username="ustoz").exists():
            User.objects.create_user("ustoz", password="ustoz123", role="teacher",
                                     first_name="Aziza", last_name="Karimova")
        if not User.objects.filter(username="oquvchi").exists():
            User.objects.create_user("oquvchi", password="oquvchi123", role="student",
                                     first_name="Ali", last_name="Valiyev", school_class=classes[2])
        self.stdout.write(self.style.SUCCESS(
            "Tayyor. O'qituvchi: ustoz / ustoz123 — O'quvchi (10-A): oquvchi / oquvchi123"))
