# leads/utils.py

import logging
from django.db import transaction
from django.contrib.auth import get_user_model

from profiles.models import DepartmentMembership
from .models import DepartmentAssignmentPointer, LeadAssignmentLog

logger = logging.getLogger(__name__)
User = get_user_model()

def allocate_lead_to_user(lead):
    """
    Round-robin assign an on-duty L2/L3 user in the lead's department,
    set lead.lead_manager, save, and write a LeadAssignmentLog.
    """
    dept = lead.department
    if not dept:
        logger.warning("No department on lead %s – skipping allocation", lead.pk)
        return None

    # fetch or create the pointer
    pointer, _ = DepartmentAssignmentPointer.objects.get_or_create(department=dept)

    # grab all level 2/3 memberships in that dept
    memberships = (
        DepartmentMembership.objects
        .filter(department=dept, level__in=(2,3))
        .select_related("user__profile")
    )
    # only keep on-duty users
    eligible = [
        m for m in memberships
        if getattr(m.user.profile, "is_on_duty", False)
    ]

    if not eligible:
        logger.warning("No on-duty users in %r – cannot allocate", dept)
        return None

    # sort to keep order stable
    eligible.sort(key=lambda m: m.user_id)
    user_ids = [m.user_id for m in eligible]

    # figure out where to start in the round-robin
    try:
        last = pointer.last_assigned_id
        start = user_ids.index(last) + 1
    except (ValueError, TypeError):
        start = 0

    # **HERE** we define chosen_id
    idx = start % len(user_ids)
    chosen_id = user_ids[idx]

    # now atomically update pointer + lead + log
    with transaction.atomic():
        ptr = DepartmentAssignmentPointer.objects.select_for_update().get(pk=pointer.pk)
        ptr.last_assigned_id = chosen_id
        ptr.save(update_fields=["last_assigned"])

        lead.lead_manager_id = chosen_id
        lead.save(update_fields=["lead_manager"])

        log = LeadAssignmentLog.objects.create(
            lead        = lead,
            assigned_to_id = chosen_id,
            department  = dept,
        )
        logger.info("Lead %s assigned to %s (log %s)", lead.pk, chosen_id, log.pk)

    return chosen_id