"""Zielgruppen gehören zur Veranstaltung; die bisherigen werden zu Vorlagen (ADR 0010)."""

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models

CRITERIA = ("min_age", "max_age", "genders", "min_weight", "max_weight", "min_grade", "max_grade")


def copy_to_events(apps, schema_editor):
    Event = apps.get_model("events", "Event")
    TargetGroup = apps.get_model("events", "TargetGroup")
    for event in Event.objects.prefetch_related("old_target_groups__interests"):
        for template in event.old_target_groups.all():
            group = TargetGroup.objects.create(
                event=event, name=template.name, **{name: getattr(template, name) for name in CRITERIA}
            )
            group.interests.set(template.interests.all())


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0003_guests"),
        ("members", "0002_interests"),
    ]

    operations = [
        migrations.RenameModel("TargetGroup", "TargetGroupTemplate"),
        migrations.AlterModelOptions(
            name="targetgrouptemplate",
            options={
                "ordering": ("name",),
                "verbose_name": "Zielgruppen-Vorlage",
                "verbose_name_plural": "Zielgruppen-Vorlagen",
            },
        ),
        migrations.RenameField("event", "target_groups", "old_target_groups"),
        migrations.CreateModel(
            name="TargetGroup",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "min_age",
                    models.PositiveSmallIntegerField(
                        blank=True,
                        help_text="Nach Jahrgang: Jahr des Termins minus Geburtsjahr.",
                        null=True,
                        verbose_name="Alter ab",
                    ),
                ),
                ("max_age", models.PositiveSmallIntegerField(blank=True, null=True, verbose_name="Alter bis")),
                (
                    "genders",
                    models.JSONField(
                        blank=True, default=list, help_text="Leer heißt: alle.", verbose_name="Geschlecht"
                    ),
                ),
                (
                    "min_weight",
                    models.DecimalField(
                        blank=True,
                        decimal_places=1,
                        max_digits=4,
                        null=True,
                        validators=[django.core.validators.MinValueValidator(0)],
                        verbose_name="Gewicht ab (kg)",
                    ),
                ),
                (
                    "max_weight",
                    models.DecimalField(
                        blank=True,
                        decimal_places=1,
                        max_digits=4,
                        null=True,
                        validators=[django.core.validators.MaxValueValidator(250)],
                        verbose_name="Gewicht bis (kg)",
                    ),
                ),
                (
                    "min_grade",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("kyu9", "9. Kyu (weiß)"),
                            ("kyu8", "8. Kyu (weiß-gelb)"),
                            ("kyu7", "7. Kyu (gelb)"),
                            ("kyu6", "6. Kyu (gelb-orange)"),
                            ("kyu5", "5. Kyu (orange)"),
                            ("kyu4", "4. Kyu (orange-grün)"),
                            ("kyu3", "3. Kyu (grün)"),
                            ("kyu2", "2. Kyu (blau)"),
                            ("kyu1", "1. Kyu (braun)"),
                            ("dan1", "1. Dan (schwarz)"),
                            ("dan2", "2. Dan (schwarz)"),
                            ("dan3", "3. Dan (schwarz)"),
                            ("dan4", "4. Dan (schwarz)"),
                            ("dan5", "5. Dan (schwarz)"),
                            ("dan6", "6. Dan (rot-weiß)"),
                            ("dan7", "7. Dan (rot-weiß)"),
                            ("dan8", "8. Dan (rot-weiß)"),
                            ("dan9", "9. Dan (rot)"),
                            ("dan10", "10. Dan (rot)"),
                        ],
                        max_length=5,
                        verbose_name="Graduierung ab",
                    ),
                ),
                (
                    "max_grade",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("kyu9", "9. Kyu (weiß)"),
                            ("kyu8", "8. Kyu (weiß-gelb)"),
                            ("kyu7", "7. Kyu (gelb)"),
                            ("kyu6", "6. Kyu (gelb-orange)"),
                            ("kyu5", "5. Kyu (orange)"),
                            ("kyu4", "4. Kyu (orange-grün)"),
                            ("kyu3", "3. Kyu (grün)"),
                            ("kyu2", "2. Kyu (blau)"),
                            ("kyu1", "1. Kyu (braun)"),
                            ("dan1", "1. Dan (schwarz)"),
                            ("dan2", "2. Dan (schwarz)"),
                            ("dan3", "3. Dan (schwarz)"),
                            ("dan4", "4. Dan (schwarz)"),
                            ("dan5", "5. Dan (schwarz)"),
                            ("dan6", "6. Dan (rot-weiß)"),
                            ("dan7", "7. Dan (rot-weiß)"),
                            ("dan8", "8. Dan (rot-weiß)"),
                            ("dan9", "9. Dan (rot)"),
                            ("dan10", "10. Dan (rot)"),
                        ],
                        max_length=5,
                        verbose_name="Graduierung bis",
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        blank=True, help_text="Optional, z. B. „U11“.", max_length=80, verbose_name="Bezeichnung"
                    ),
                ),
                (
                    "event",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="target_groups",
                        to="events.event",
                    ),
                ),
                (
                    "interests",
                    models.ManyToManyField(
                        blank=True,
                        help_text="Passt, wenn das Mitglied eines davon gewählt hat.",
                        to="members.interest",
                        verbose_name="Interessen",
                    ),
                ),
            ],
            options={"verbose_name": "Zielgruppe", "verbose_name_plural": "Zielgruppen", "ordering": ("pk",)},
        ),
        migrations.RunPython(copy_to_events, migrations.RunPython.noop),
        migrations.RemoveField("event", "old_target_groups"),
    ]
