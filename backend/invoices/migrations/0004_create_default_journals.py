from django.db import migrations


def create_default_journals(apps, schema_editor):
    Journal = apps.get_model("invoices", "Journal")
    Journal.objects.get_or_create(name="Cash", defaults={"type": "cash"})
    Journal.objects.get_or_create(name="Bank", defaults={"type": "bank"})


def reverse_default_journals(apps, schema_editor):
    Journal = apps.get_model("invoices", "Journal")
    Journal.objects.filter(name__in=["Cash", "Bank"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("invoices", "0003_customer_invoiceline_journal_payment_tag_and_more"),
    ]

    operations = [
        migrations.RunPython(create_default_journals, reverse_default_journals),
    ]
