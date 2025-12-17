from rest_framework import permissions

class IsPremium(permissions.BasePermission):
    """
    Permite acesso apenas a usuários Premium ou Premium Plus.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
            
        # Lógica temporária até termos UserProfile completo em BD-001
        # Assumindo que o profile será criado em accounts ou api
        if hasattr(request.user, 'profile') and request.user.profile.plan:
             plan = str(request.user.profile.plan).upper()
             return plan in ['PREMIUM', 'PREMIUM_PLUS']
        
        # Para facilitar desenvolvimento/teste se não tiver profile ainda:
        # Se for superuser, libera
        if request.user.is_superuser:
            return True
            
        return False
