# profiles/apps.py

from django.apps import AppConfig

class ProfilesConfig(AppConfig):
    name = 'profiles'
    def ready(self):
        import profiles.signals   # ensures the signal handler is registered
