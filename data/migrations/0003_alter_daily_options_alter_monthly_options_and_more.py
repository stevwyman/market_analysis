# Generated by Django 4.1.7 on 2023-04-27 09:14

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("data", "0002_dataprovider_description_alter_dataprovider_name"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="daily",
            options={"ordering": ["date"]},
        ),
        migrations.AlterModelOptions(
            name="monthly",
            options={"ordering": ["date"]},
        ),
        migrations.AlterModelOptions(
            name="weekly",
            options={"ordering": ["date"]},
        ),
        migrations.AddConstraint(
            model_name="security",
            constraint=models.UniqueConstraint(
                fields=("symbol", "data_provider"),
                name="unique_symbol_data_provider_combination",
            ),
        ),
    ]
