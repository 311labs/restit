# Generated by Django 4.1.1 on 2022-09-24 21:56

from django.db import migrations, models
import django.db.models.deletion
import rest.models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0010_delete_authtoken'),
    ]

    operations = [
        migrations.CreateModel(
            name='AuthToken',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('token', models.TextField(db_index=True, unique=True)),
                ('role', models.CharField(blank=True, default=None, max_length=128, null=True)),
                ('signature', models.CharField(blank=True, db_index=True, default=None, max_length=128, null=True)),
                ('member', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='auth_tokens', to='account.member')),
            ],
            bases=(models.Model, rest.models.RestModel),
        ),
    ]
