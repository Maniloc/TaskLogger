from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0006_alter_conversation_id_alter_message_created_at_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="message",
            name="file",
            field=models.FileField(blank=True, null=True, upload_to="chat/%Y/%m/", verbose_name="Файл"),
        ),
        migrations.AddField(
            model_name="message",
            name="file_name",
            field=models.CharField(blank=True, max_length=255, verbose_name="Имя файла"),
        ),
        migrations.AddField(
            model_name="message",
            name="file_size",
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name="Размер файла"),
        ),
        migrations.AddField(
            model_name="message",
            name="file_type",
            field=models.CharField(blank=True, max_length=20, verbose_name="Тип"),
        ),
    ]
