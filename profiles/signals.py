# profiles/signals.py

from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

@receiver(user_logged_in)
def cache_memberships(sender, user, request, **kwargs):
    """
    On login, fetch this user’s department+level info once
    and stash it into the session.
    """
    qs = user.departmentmembership_set.select_related('department').all()
    request.session['memberships'] = [
        {
            'department_id': m.department_id,
            'department_name': m.department.name,
            'level': m.level,
        }
        for m in qs
    ]
