# Generated manually for Mercado Pago Checkout Pro

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("clientes", "0001_initial"),
        ("pedidos", "0006_documentos_pagos"),
    ]

    operations = [
        migrations.CreateModel(
            name="CheckoutPago",
            fields=[
                ("checkout_id", models.AutoField(primary_key=True, serialize=False)),
                ("numero_oc", models.CharField(blank=True, max_length=30)),
                ("monto_clp", models.IntegerField()),
                ("preference_id", models.CharField(blank=True, max_length=40)),
                ("external_reference", models.CharField(max_length=64, unique=True)),
                ("payment_id", models.CharField(blank=True, max_length=40)),
                ("estado", models.CharField(choices=[("pendiente", "Esperando pago"), ("completado", "Completado"), ("fallido", "Fallido")], default="pendiente", max_length=12)),
                ("primera_orden_id", models.IntegerField(blank=True, null=True)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                ("cliente", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="clientes.cliente")),
                ("direccion", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="clientes.direccion")),
            ],
            options={"db_table": "checkout_pago"},
        ),
        migrations.AddField(
            model_name="orden",
            name="checkout_pago",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="ordenes", to="pedidos.checkoutpago"),
        ),
        migrations.AlterField(
            model_name="pago",
            name="medio",
            field=models.CharField(choices=[("webpay", "Webpay (simulado)"), ("mercadopago", "Mercado Pago"), ("transferencia", "Transferencia"), ("cheque", "Cheque"), ("efectivo", "Efectivo"), ("devolucion", "Devolución")], max_length=14),
        ),
    ]
