# Generated manually for performance optimization

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0002_alter_threadmodel_id_alter_threadmodelvote_id'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='threadmodelvote',
            index=models.Index(fields=['object'], name='app_threadm_object__idx'),
        ),
        migrations.AddIndex(
            model_name='threadmodelvote',
            index=models.Index(fields=['object', 'value'], name='app_threadm_object__cov_idx'),
        ),
    ]
