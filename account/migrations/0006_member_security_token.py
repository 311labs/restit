# Generated by Django 4.0.3 on 2022-03-29 20:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0005_member_auth_code_expires'),
    ]

    operations = [
        migrations.AddField(
            model_name='member',
            name='security_token',
            field=models.CharField(blank=True, db_index=True, default=None, max_length=64, null=True),
        ),
    ]