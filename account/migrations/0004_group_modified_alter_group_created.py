# Generated by Django 4.0.2 on 2022-02-27 04:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0003_member_phone_number'),
    ]

    operations = [
        migrations.AddField(
            model_name='group',
            name='modified',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AlterField(
            model_name='group',
            name='created',
            field=models.DateTimeField(auto_now_add=True),
        ),
    ]
