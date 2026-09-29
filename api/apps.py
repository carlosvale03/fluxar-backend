from django.apps import AppConfig


class ApiConfig(AppConfig):
    name = 'api'

    def ready(self):
        import api.signals
        import core.checks  # noqa: F401  registra a checagem da SECRET_KEY
