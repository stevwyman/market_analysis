# Generated by Django 4.1.7 on 2023-04-28 11:40

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("data", "0005_weeklyupdate_monthlyupdate_dailyupdate_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="dailyupdate",
            name="date",
            field=models.DateField(auto_now_add=True),
        ),
        migrations.AlterField(
            model_name="monthlyupdate",
            name="date",
            field=models.DateField(auto_now_add=True),
        ),
        migrations.AlterField(
            model_name="weeklyupdate",
            name="date",
            field=models.DateField(auto_now_add=True),
        ),
    ]
