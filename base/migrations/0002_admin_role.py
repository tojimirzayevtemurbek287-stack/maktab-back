from django.db import migrations, models


def make_superusers_admin(apps, schema_editor):
    """Avval yaratilgan superuserlar ham administrator rolini olsin."""
    User = apps.get_model("base", "User")
    User.objects.filter(is_superuser=True).update(role="admin")


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("admin", "Administrator"),
                    ("teacher", "O'qituvchi"),
                    ("student", "O'quvchi"),
                ],
                default="student",
                max_length=10,
            ),
        ),
        migrations.RunPython(make_superusers_admin, migrations.RunPython.noop),
    ]
