# Generated by Django 3.2.5 on 2021-10-25 20:47

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('alerting', '0002_auto_20211025_1449'),
    ]

    operations = [
        migrations.RenameField(
            model_name='alert',
            old_name='currency',
            new_name='symbol',
        ),
    ]
