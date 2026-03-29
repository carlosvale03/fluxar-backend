from django.apps import AppConfig

class GoalsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'goals'

    def ready(self):
        print("[DEBUG GOALS] Carregando sinais de automação de metas...")
        import goals.signals
