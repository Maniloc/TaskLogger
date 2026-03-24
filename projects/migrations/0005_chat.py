from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0004_task_dates'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Conversation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('participants', models.ManyToManyField(
                    related_name='conversations',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Участники'
                )),
            ],
            options={'verbose_name': 'Диалог', 'verbose_name_plural': 'Диалоги',
                     'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='Message',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('text', models.TextField('Текст')),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('is_read', models.BooleanField(default=False, db_index=True)),
                ('conversation', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='messages',
                    to='projects.conversation'
                )),
                ('sender', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='sent_messages',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Отправитель'
                )),
            ],
            options={'verbose_name': 'Сообщение', 'verbose_name_plural': 'Сообщения',
                     'ordering': ['created_at']},
        ),
    ]
