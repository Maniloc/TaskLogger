from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("projects", "0016_conv_sort_order")]
    operations = [
        migrations.CreateModel(
            name="PushSubscription",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("endpoint", models.TextField(verbose_name="Endpoint")),
                ("p256dh",   models.TextField(verbose_name="p256dh key")),
                ("auth",     models.TextField(verbose_name="Auth key")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="push_subscriptions",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"verbose_name": "Push-подписка"},
        ),
    ]
