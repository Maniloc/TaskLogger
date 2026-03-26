from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("projects", "0014_message_reply")]
    operations = [
        migrations.AddField(
            model_name="conversationsettings",
            name="is_pinned",
            field=models.BooleanField(default=False, verbose_name="Закреплён"),
        ),
        migrations.AddField(
            model_name="conversationsettings",
            name="pin_order",
            field=models.PositiveIntegerField(default=0, verbose_name="Порядок закрепления"),
        ),
        # Saved messages conversation — self-conversation flag
        migrations.AddField(
            model_name="conversation",
            name="is_saved",
            field=models.BooleanField(default=False, verbose_name="Избранное"),
        ),
    ]
