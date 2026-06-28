from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0035_add_is_featured_to_biography'),
    ]

    operations = [
        migrations.AddField(
            model_name='biography',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to='biography/images', verbose_name='Image'),
        ),
        migrations.AddField(
            model_name='biography',
            name='featured_summary_ar',
            field=models.CharField(
                blank=True,
                help_text='نبذة مختصرة تظهر في قسم الأعلام المميزين في الصفحة الرئيسية',
                max_length=500,
                verbose_name='Featured Summary (Arabic)',
            ),
        ),
        migrations.AddField(
            model_name='biography',
            name='featured_summary_en',
            field=models.CharField(
                blank=True,
                help_text='Short summary shown in the Featured Biographies card on the home page',
                max_length=500,
                verbose_name='Featured Summary (English)',
            ),
        ),
    ]
