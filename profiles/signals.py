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

@receiver(user_logged_in)
def cache_user_data(sender, user, request, **kwargs):
    """
    On login, stash:
     - Department memberships
     - User’s full name
     - User’s job title
    into the session so you don’t hit the DB again.
    """
    # 1) Memberships (existing code)
    qs = user.departmentmembership_set.select_related('department').all()
    request.session['memberships'] = [
        {
            'department_id':   m.department_id,
            'department_name': m.department.name,
            'level':           m.level,
        }
        for m in qs
    ]

    # 2) Full name
    full_name = user.get_full_name() or user.username
    request.session['user_full_name'] = full_name

    # 3) Job title (falls back if somehow missing)
    job_title = getattr(user.profile, 'job_title', 'Not Defined Yet')
    request.session['job_title'] = job_title