from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0031_biography_hometown_m2m'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='Note',
            new_name='Reading',
        ),
        migrations.RemoveField(
            model_name='reading',
            name='short_name_ar',
        ),
        migrations.RemoveField(
            model_name='reading',
            name='short_name_en',
        ),
        migrations.RemoveField(
            model_name='reading',
            name='long_name_ar',
        ),
        migrations.RemoveField(
            model_name='reading',
            name='long_name_en',
        ),
        migrations.AddField(
            model_name='reading',
            name='description_ar',
            field=models.TextField(verbose_name='Description (Arabic)', default=''),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='reading',
            name='description_en',
            field=models.TextField(verbose_name='Description (English)', blank=True),
        ),
        migrations.AlterModelOptions(
            name='reading',
            options={
                'verbose_name': 'المقروء',
                'verbose_name_plural': 'المقروءات',
                'ordering': ['id'],
            },
        ),
        migrations.AlterField(
            model_name='teacherstudentrelationship',
            name='notes',
            field=models.ManyToManyField(
                blank=True, related_name='relationships',
                to='core.reading', verbose_name='المقروءات',
            ),
        ),
    ]
