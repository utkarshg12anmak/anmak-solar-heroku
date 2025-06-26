#core/apps.py
from django.apps import AppConfig
from django.db.models.signals import post_migrate
from django.contrib.auth import get_user_model


def create_default_superuser(sender, **kwargs):
    """
    After migrations, ensure a default superuser exists with static credentials.
    """
    User = get_user_model()
    username = 'admin'
    email = 'admin@anmaksolar.com'
    password = 'admin123!'

    if not User.objects.filter(username=username).exists():
        User.objects.create_superuser(username=username, email=email, password=password)
        print(f"Created default superuser '{username}'")


class CoreConfig(AppConfig):
    name = 'core'

    def ready(self):
        post_migrate.connect(create_default_superuser, sender=self)
