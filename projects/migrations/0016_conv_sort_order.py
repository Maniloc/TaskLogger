from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("projects", "0015_pin_saved")]
    operations = [
        migrations.AddField(
            model_name="conversationsettings",
            name="sort_order",
            field=models.IntegerField(default=0, verbose_name="Порядок сортировки"),
        ),
    ]
