from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('landing', '0018_add_featured_biographies_section_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='sitesettings',
            name='biography_placeholder_image',
            field=models.ImageField(blank=True, null=True, upload_to='landing/biography_placeholder', verbose_name='Biography placeholder image'),
        ),
    ]
