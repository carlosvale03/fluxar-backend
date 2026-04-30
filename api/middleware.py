from django.http import JsonResponse
from .models import GlobalSetting
from django.conf import settings

class MaintenanceModeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Permitir acesso a rotas de admin e login mesmo em manutenção
        # Também permitir acesso se for um superuser logado
        path = request.path
        
        # Rotas permitidas (ajustar conforme necessário)
        allowed_paths = [
            '/api/admin/',
            '/api/auth/login/',
            '/api/auth/token/refresh/',
        ]
        
        is_allowed_path = any(path.startswith(p) for p in allowed_paths)
        is_admin_user = request.user.is_authenticated and request.user.is_staff

        if not is_allowed_path and not is_admin_user:
            try:
                maintenance_setting = GlobalSetting.objects.get(key='maintenance_mode')
                if maintenance_setting.value.lower() == 'true':
                    return JsonResponse(
                        {
                            "detail": "O sistema está em manutenção programada. Por favor, tente novamente mais tarde.",
                            "code": "maintenance_mode"
                        },
                        status=503
                    )
            except GlobalSetting.DoesNotExist:
                # Se não existir a configuração, o sistema segue online
                pass

        response = self.get_response(request)
        return response
