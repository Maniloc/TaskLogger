from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0010_invitetoken'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Online status on UserProfile
        migrations.AddField(
            model_name='userprofile',
            name='last_seen',
            field=models.DateTimeField(null=True, blank=True, verbose_name='Последний визит'),
        ),
        # Conversation: title for group chats + is_group flag
        migrations.AddField(
            model_name='conversation',
            name='title',
            field=models.CharField(max_length=100, blank=True, verbose_name='Название беседы'),
        ),
        migrations.AddField(
            model_name='conversation',
            name='is_group',
            field=models.BooleanField(default=False, verbose_name='Групповой чат'),
        ),
        migrations.AddField(
            model_name='conversation',
            name='created_by',
            field=models.ForeignKey(
                null=True, blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='created_conversations',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Создатель',
            ),
        ),
        # Per-conversation mute setting
        migrations.CreateModel(
            name='ConversationSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('is_muted', models.BooleanField(default=False, verbose_name='Уведомления отключены')),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='conversation_settings',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('conversation', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='settings',
                    to='projects.conversation',
                )),
            ],
            options={
                'unique_together': {('user', 'conversation')},
                'verbose_name': 'Настройки беседы',
            },
        ),
    ]
