# Generated by Django 3.2.5 on 2021-10-27 12:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('alerting', '0004_job'),
    ]

    operations = [
        migrations.AddField(
            model_name='alert',
            name='published_time',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
