from django.db import migrations

DEFAULT_TAGS = [
    {"name": "Urgent", "color": "#ef4444"},
    {"name": "VIP", "color": "#f59e0b"},
    {"name": "Wholesale", "color": "#3b82f6"},
    {"name": "Retail", "color": "#10b981"},
    {"name": "Services", "color": "#8b5cf6"},
    {"name": "Logistics", "color": "#06b6d4"},
    {"name": "Recurring", "color": "#ec4899"},
    {"name": "Tax-Exempt", "color": "#64748b"},
]


def create_default_tags(apps, schema_editor):
    Tag = apps.get_model("invoices", "Tag")
    for t in DEFAULT_TAGS:
        Tag.objects.get_or_create(name=t["name"], defaults={"color": t["color"]})


def reverse_default_tags(apps, schema_editor):
    Tag = apps.get_model("invoices", "Tag")
    tag_names = [t["name"] for t in DEFAULT_TAGS]
    Tag.objects.filter(name__in=tag_names).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("invoices", "0004_create_default_journals"),
    ]

    operations = [
        migrations.RunPython(create_default_tags, reverse_default_tags),
    ]
