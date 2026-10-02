from datetime import date, timedelta

from django.db.models import Count, Q

from .models import Reminder, Pet

# Window (in days) used for the "due soon" navigation badge.
DUE_SOON_WINDOW_DAYS = 7


def petcare_badges(request):
    """Notification counters rendered in the navigation bar.

    Runs on every authenticated request, so it issues a single grouped query
    instead of four separate ``COUNT`` queries.
    """
    if not request.user.is_authenticated:
        return {}

    today = date.today()
    due_soon_limit = today + timedelta(days=DUE_SOON_WINDOW_DAYS)

    counts = (
        Reminder.objects.filter(owner=request.user, is_completed=False)
        .aggregate(
            overdue=Count('pk', filter=Q(due_date__lt=today)),
            today=Count('pk', filter=Q(due_date=today)),
            due_soon=Count(
                'pk',
                filter=Q(due_date__gt=today, due_date__lte=due_soon_limit),
            ),
        )
    )

    overdue_count = counts['overdue']
    today_count = counts['today']

    return {
        'badge_overdue_count': overdue_count,
        'badge_today_count': today_count,
        'badge_due_soon_count': counts['due_soon'],
        'badge_urgent_total': overdue_count + today_count,
        'nav_total_pets': Pet.objects.filter(owner=request.user).count(),
    }
