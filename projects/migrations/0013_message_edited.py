from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('projects', '0012_project_members')]
    operations = [
        migrations.AddField(
            model_name='message',
            name='is_edited',
            field=models.BooleanField(default=False, verbose_name='Изменено'),
        ),
        migrations.AddField(
            model_name='message',
            name='edited_at',
            field=models.DateTimeField(null=True, blank=True, verbose_name='Изменено в'),
        ),
    ]
