from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sinav', '0022_approved_violation_count'),
    ]

    operations = [
        migrations.AddField(
            model_name='examsession',
            name='proximity_mode',
            field=models.CharField(choices=[('STANDARD', 'Bütün komşu sıralar'), ('CLOSEST', 'En yakın komşular öncelikli')], default='STANDARD', max_length=10, verbose_name='yakınlık önceliği'),
        ),
    ]
