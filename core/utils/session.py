# core/utils/session.py

from django.db.models import Q
from core.models import SiteSettings
from customers.models import City, CustomerSource, Designation
from profiles.models import DepartmentMembership

def set_session_data(request, user):
    # 1. Department memberships
    memberships = DepartmentMembership.objects.filter(user=user).select_related(
        'department__dept_type', 'department__category'
    )
    session_memberships = []
    for m in memberships:
        session_memberships.append({
            'department_id': m.department_id,
            'department_name': m.department.name,
            'level': m.level,
            'dept_type': m.department.dept_type.name,
            'category': m.department.category.name
        })
    request.session['memberships'] = session_memberships

    # 2. Active membership
    active = next((
        m for m in session_memberships
        if m['dept_type'] == 'Customer Support' and m['category'] == 'Lead Qualification Team'
    ), None)
    if active:
        request.session['active_membership'] = active

    # 3. City permissions
    city_qs = City.objects.filter(Q(view_only_users=user) | Q(view_edit_users=user)).distinct()
    request.session['viewable_city_ids'] = list(city_qs.values_list('id', flat=True))

    # 4. Lookups
    request.session['designation_map'] = {d.id: d.title for d in Designation.objects.all()}
    request.session['customer_source_map'] = {s.id: s.name for s in CustomerSource.objects.all()}

    # 5. Site settings
    settings_obj = SiteSettings.objects.first()
    if settings_obj:
        request.session['site_settings'] = {
            'session_timeout_hours': settings_obj.session_timeout_hours
        }

    # 6. User info
    request.session['user_full_name'] = user.get_full_name()
    request.session['job_title'] = getattr(user, 'job_title', 'Not Defined Yet')
