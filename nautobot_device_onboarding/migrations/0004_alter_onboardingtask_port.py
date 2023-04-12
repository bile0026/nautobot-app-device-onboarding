# Generated by Django 3.2.18 on 2023-04-12 18:09

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("nautobot_device_onboarding", "0003_onboardingtask_label"),
    ]

    operations = [
        migrations.AlterField(
            model_name="onboardingtask",
            name="port",
            field=models.PositiveIntegerField(
                default=22,
                validators=[
                    django.core.validators.MinValueValidator(1),
                    django.core.validators.MaxValueValidator(65535),
                ],
            ),
        ),
    ]
