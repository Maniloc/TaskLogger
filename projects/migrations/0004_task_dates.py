from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0003_userprofile'),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='start_date',
            field=models.DateField(blank=True, null=True, verbose_name='Дата начала'),
        ),
        migrations.AddField(
            model_name='task',
            name='due_date',
            field=models.DateField(blank=True, null=True, verbose_name='Крайний срок'),
        ),
    ]
