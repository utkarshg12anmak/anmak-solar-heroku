from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from core.utils.session import set_session_data  # <-- import from core

@receiver(user_logged_in)
def post_login_handler(sender, user, request, **kwargs):
    set_session_data(request, user)
