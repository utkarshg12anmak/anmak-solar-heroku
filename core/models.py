from django.db import models

class SiteSettings(models.Model):
    # Enforce a single row—use Django’s “Singleton” pattern or simply grab the first
    session_timeout_hours = models.PositiveIntegerField(
        default=24,
        help_text="How many hours before a user’s session should expire."
    )

    def __str__(self):
        return "Site Settings"

    class Meta:
        verbose_name = "Site Settings"
        verbose_name_plural = "Site Settings"
