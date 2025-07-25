# Generated by Django 5.2.1 on 2025-06-27 20:35

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("items", "0005_pricerule_available"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="pricerule",
            options={"ordering": ["price_book__name", "item__product_name"]},
        ),
        migrations.AlterUniqueTogether(
            name="pricerule",
            unique_together={("price_book", "item")},
        ),
    ]
