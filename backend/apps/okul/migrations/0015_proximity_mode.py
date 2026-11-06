from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('okul', '0014_section_spread'),
    ]

    operations = [
        migrations.AddField(
            model_name='schoolconfig',
            name='default_proximity_mode',
            field=models.CharField(choices=[('STANDARD', 'Bütün komşu sıralar'), ('CLOSEST', 'En yakın komşular öncelikli')], default='STANDARD', max_length=10, verbose_name='yakınlık önceliği varsayılanı'),
        ),
    ]
