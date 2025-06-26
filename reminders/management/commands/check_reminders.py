# reminders/management/commands/check_reminders.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from reminders.models import Reminder, ReminderSettings
from django.contrib.contenttypes.models import ContentType

class Command(BaseCommand):
    help = "Check all Reminder rows and send pings or mark overdue."

    def handle(self, *args, **options):
        now = timezone.now()

        # 1) Load global default ping interval (if any)
        try:
            global_settings = ReminderSettings.objects.first()
            default_ping = global_settings.default_ping_before_minutes
        except ReminderSettings.DoesNotExist:
            default_ping = 10  # fallback

        # 2) Find all DUE reminders whose ping moment has arrived
        due_qs = Reminder.objects.filter(status='DUE')
        for r in due_qs:
            pb = r.ping_before_override if r.ping_before_override is not None else default_ping
            ping_moment = r.reminder_time - timezone.timedelta(minutes=pb)
            # If we've reached or passed the ping moment, but are still before reminder_time:
            if ping_moment <= now < r.reminder_time:
                # Send an actual ping (you must implement send_ping yourself).
                # Example placeholder:
                self.stdout.write(f"PING → Reminder#{r.id} for User {r.owner}. Message: {r.message}")
                # TODO: replace the above with real notification (email, in-app, etc.)
                r.status = 'PINGED'
                r.save()

        # 3) Find all not‐yet‐completed reminders whose final time has passed
        overdue_qs = Reminder.objects.filter(
            status__in=['DUE', 'PINGED'],
            reminder_time__lte=now
        )
        for r in overdue_qs:
            self.stdout.write(f"OVERDUE → Reminder#{r.id} for User {r.owner}. Message: {r.message}")
            r.status = 'OVERDUE'
            r.save()

        self.stdout.write(self.style.SUCCESS("check_reminders: done."))