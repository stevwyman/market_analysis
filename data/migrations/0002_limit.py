# Generated by Django 4.2.1 on 2023-06-05 12:02

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("data", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Limit",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("price", models.DecimalField(decimal_places=6, max_digits=16)),
                ("comment", models.TextField(blank=True, null=True)),
                (
                    "role",
                    models.PositiveSmallIntegerField(
                        choices=[(1, "daily"), (2, "weekly"), (3, "monthly")], default=1
                    ),
                ),
                (
                    "security",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="data.security"
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
    ]
