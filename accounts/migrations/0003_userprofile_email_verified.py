from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0002_userprofile_role'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='email_verified',
            field=models.BooleanField(
                default=True, editable=False, verbose_name='Имейлът е потвърден'
            ),
        ),
    ]
