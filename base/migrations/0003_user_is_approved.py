from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0002_admin_role"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="is_approved",
            field=models.BooleanField(default=True),
        ),
    ]
