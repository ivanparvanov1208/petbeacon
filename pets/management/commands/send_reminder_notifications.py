from datetime import datetime, time, timedelta
from urllib.parse import urljoin

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand, CommandError
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.dateformat import format as date_format
from django.utils.translation import gettext as _, override

from pets.models import Reminder


class Command(BaseCommand):
    help = "Send email reminders that are due within the configured lead time."

    def handle(self, *args, **options):
        if not settings.EMAIL_HOST or not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
            raise CommandError(
                "Configure EMAIL_HOST, EMAIL_HOST_USER, and EMAIL_HOST_PASSWORD in .env first."
            )
        if settings.EMAIL_USE_TLS and settings.EMAIL_USE_SSL:
            raise CommandError("Enable either EMAIL_USE_TLS or EMAIL_USE_SSL, not both.")
        if not settings.DEFAULT_FROM_EMAIL:
            raise CommandError("Configure DEFAULT_FROM_EMAIL in .env first.")

        now = timezone.localtime()
        lead_hours = max(1, settings.REMINDER_EMAIL_LEAD_HOURS)
        window_end = now + timedelta(hours=lead_hours)
        reminders = Reminder.objects.filter(
            is_completed=False,
            email_notification_enabled=True,
            email_notification_sent_at__isnull=True,
            owner__is_active=True,
        ).exclude(owner__email='').filter(
            due_date__gte=now.date(), due_date__lte=window_end.date()
        ).select_related('owner', 'pet').order_by('due_date', 'due_time', 'pk')

        sent = 0
        failed = 0
        for reminder in reminders:
            due_time = reminder.due_time or time(9, 0)
            due_at = timezone.make_aware(
                datetime.combine(reminder.due_date, due_time), timezone.get_current_timezone()
            )
            if not now <= due_at <= window_end:
                continue

            language = reminder.language if reminder.language in {'bg', 'en'} else settings.LANGUAGE_CODE
            try:
                with override(language):
                    context = {
                        'reminder': reminder,
                        'pet_name': reminder.pet.name if reminder.pet else None,
                        'due_text': date_format(due_at, 'DATETIME_FORMAT'),
                        'reminder_type': reminder.get_reminder_type_display(),
                        'reminder_url': urljoin(
                            settings.APP_BASE_URL + '/', reverse('pets:reminder_list')
                        ),
                        'site_url': settings.APP_BASE_URL,
                    }
                    subject = _("PetBeacon reminder: %(title)s") % {'title': reminder.title}
                    text_body = render_to_string('emails/reminder_notification.txt', context)
                    html_body = render_to_string('emails/reminder_notification.html', context)
                    message = EmailMultiAlternatives(
                        subject=subject,
                        body=text_body,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        to=[reminder.owner.email],
                    )
                    message.attach_alternative(html_body, 'text/html')
                    message.send(fail_silently=False)
                reminder.email_notification_sent_at = timezone.now()
                reminder.save(update_fields=['email_notification_sent_at'])
                sent += 1
            except Exception as error:
                failed += 1
                self.stderr.write(self.style.ERROR(
                    f"Reminder {reminder.pk}: email delivery failed ({error.__class__.__name__})."
                ))

        self.stdout.write(self.style.SUCCESS(f"Sent {sent} reminder email(s); {failed} failed."))
