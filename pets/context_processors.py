from datetime import date
from .models import Reminder, Pet


def petcare_badges(request):
    if not request.user.is_authenticated:
        return {}

    today = date.today()
    user_reminders = Reminder.objects.filter(owner=request.user, is_completed=False)
    overdue_count = user_reminders.filter(due_date__lt=today).count()
    today_count = user_reminders.filter(due_date=today).count()
    due_soon_count = user_reminders.filter(due_date__gte=today, due_date__lte=today.replace(day=min(today.day + 7, 28))).count()

    total_pets = Pet.objects.filter(owner=request.user).count()

    return {
        'badge_overdue_count': overdue_count,
        'badge_today_count': today_count,
        'badge_due_soon_count': due_soon_count,
        'badge_urgent_total': overdue_count + today_count,
        'nav_total_pets': total_pets,
    }
