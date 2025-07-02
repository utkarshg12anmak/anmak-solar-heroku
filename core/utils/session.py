# core/utils/session.py

from django.db.models import Q
from core.models import SiteSettings
from customers.models import City, CustomerSource, Designation
from profiles.models import DepartmentMembership
from collections import defaultdict
from django.contrib.auth import get_user_model


def set_session_data(request, user):
    # 1. Department memberships
    memberships = DepartmentMembership.objects.filter(user=user).select_related(
        'department__dept_type', 'department__category'
    )
    session_memberships = []
    department_ids = set()

    for m in memberships:
        session_memberships.append({
            'department_id': m.department_id,
            'department_name': m.department.name,
            'level': m.level,
            'dept_type': m.department.dept_type.name,
            'category': m.department.category.name
        })
        department_ids.add(m.department_id)

    request.session['memberships'] = session_memberships

    # 2. Active membership (Customer Support → Lead Qualification)
    active = next((
        m for m in session_memberships
        if m['dept_type'].lower() == 'customer support' and m['category'].lower() == 'lead qualification team'
    ), None)
    if active:
        request.session['active_membership'] = active

    # 3. City permissions
    city_qs = City.objects.filter(Q(view_only_users=user) | Q(view_edit_users=user)).distinct()
    request.session['viewable_city_ids'] = list(city_qs.values_list('id', flat=True))

    # 4. Lookup Tables
    request.session['designation_map'] = {
        str(d.id): d.title for d in Designation.objects.all()
    } if Designation.objects.exists() else {}

    request.session['customer_source_map'] = {
        str(s.id): s.name for s in CustomerSource.objects.all()
    } if CustomerSource.objects.exists() else {}

    # 5. Site Settings
    settings_obj = SiteSettings.objects.first()
    request.session['site_settings'] = {
        'session_timeout_hours': settings_obj.session_timeout_hours if settings_obj else 24
    }

    # 6. User Info
    User = get_user_model()
    request.session['user_full_name'] = user.get_full_name()
    job_title = getattr(getattr(user, "profile", None), "job_title", "Not Defined Yet")
    request.session['job_title'] = job_title



    # 7. Department Hierarchy Map (only for departments user belongs to)
    dept_user_map = defaultdict(lambda: defaultdict(list))  # dept_id → level → [user_ids]

    all_memberships = DepartmentMembership.objects.filter(department_id__in=department_ids)
    for m in all_memberships:
        dept_user_map[m.department_id][m.level].append(m.user_id)

    # Convert defaultdict to normal dict for JSON serialization in session
    request.session['department_user_map'] = {
        dept_id: {level: user_ids for level, user_ids in levels.items()}
        for dept_id, levels in dept_user_map.items()
    }
