from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0002_remove_task_time_spent_task_hours_task_status'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='UserProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('last_name', models.CharField(blank=True, max_length=100, verbose_name='Фамилия')),
                ('first_name', models.CharField(blank=True, max_length=100, verbose_name='Имя')),
                ('middle_name', models.CharField(blank=True, max_length=100, verbose_name='Отчество')),
                ('position', models.CharField(blank=True, max_length=200, verbose_name='Должность')),
                ('department', models.CharField(blank=True, max_length=200, verbose_name='Отдел')),
                ('user', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='profile',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Пользователь'
                )),
            ],
            options={
                'verbose_name': 'Профиль',
                'verbose_name_plural': 'Профили',
            },
        ),
    ]
