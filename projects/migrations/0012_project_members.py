from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('projects', '0011_chat_group_online'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name='ProjectMember',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('role', models.CharField(
                    max_length=20,
                    choices=[('owner','Владелец'),('executor','Исполнитель'),('observer','Наблюдатель')],
                    default='executor',
                    verbose_name='Роль',
                )),
                ('joined_at', models.DateTimeField(auto_now_add=True)),
                ('project', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='members',
                    to='projects.project',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='project_memberships',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'unique_together': {('project', 'user')},
                'verbose_name': 'Участник проекта',
                'verbose_name_plural': 'Участники проекта',
            },
        ),
        migrations.AddField(
            model_name='task',
            name='assigned_to',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='assigned_tasks',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Назначен',
            ),
        ),
    ]
