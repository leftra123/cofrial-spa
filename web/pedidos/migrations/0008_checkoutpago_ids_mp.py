from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pedidos", "0007_checkout_pago_mercadopago"),
    ]

    operations = [
        migrations.AlterField(
            model_name="checkoutpago",
            name="preference_id",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AlterField(
            model_name="checkoutpago",
            name="payment_id",
            field=models.CharField(blank=True, max_length=64),
        ),
    ]
