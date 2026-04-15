from rest_framework import permissions

class IsPremium(permissions.BasePermission):
    """
    Permite acesso apenas a usuários Premium ou Premium Plus.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
            
        # Verifica o plano diretamente no modelo User (api/models.py)
        if hasattr(request.user, 'plan'):
            plan = str(request.user.plan).upper()
            return plan in ['PREMIUM', 'PREMIUM_PLUS']
        
        # Se for superuser, libera
        if request.user.is_superuser:
            return True
            
        return False
