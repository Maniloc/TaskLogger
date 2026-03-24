from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0009_userprofile_avatar_userprofile_avatar_color"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="InviteToken",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("token", models.CharField(max_length=64, unique=True, verbose_name="Токен")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField(verbose_name="Действует до")),
                ("used", models.BooleanField(default=False)),
                ("created_by", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="invites",
                    to=settings.AUTH_USER_MODEL,
                    verbose_name="Создан кем"
                )),
                ("used_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="invite_used",
                    to=settings.AUTH_USER_MODEL,
                    verbose_name="Использован кем"
                )),
            ],
            options={"verbose_name": "Приглашение", "verbose_name_plural": "Приглашения"},
        ),
    ]
