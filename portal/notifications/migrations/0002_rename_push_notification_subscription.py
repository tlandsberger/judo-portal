# Umbenennung „PushSubscription“ → „PushNotificationSubscription“; die Daten bleiben erhalten.

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RenameModel(old_name="PushSubscription", new_name="PushNotificationSubscription"),
        migrations.AlterField(
            model_name="pushnotificationsubscription",
            name="user",
            field=models.ForeignKey(
                on_delete=models.deletion.CASCADE,
                related_name="push_notification_subscriptions",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterModelOptions(
            name="pushnotificationsubscription",
            options={
                "ordering": ("-created_at",),
                "verbose_name": "Gerät für Push-Benachrichtigungen",
                "verbose_name_plural": "Geräte für Push-Benachrichtigungen",
            },
        ),
    ]
