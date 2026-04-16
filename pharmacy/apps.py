from django.apps import AppConfig


class PharmacyConfig(AppConfig):
    name = 'pharmacy'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        from . import signals  # noqa: F401
