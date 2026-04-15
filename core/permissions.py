from rest_framework import permissions

class IsOwner(permissions.BasePermission):
    """
    Permite acesso apenas ao dono do objeto.
    Assume que o modelo tem um campo 'user'.
    """
    def has_object_permission(self, request, view, obj):
        # Leitura e escrita apenas para o dono
        return obj.user == request.user

class IsAuthenticatedOrPublic(permissions.BasePermission):
    """
    Permite acesso público para métodos seguros ou views marcadas explicitamente.
    (Geralmente usado globalmente se quisermos whitelist, mas aqui usaremos IsAuthenticated default)
    """
    def has_permission(self, request, view):
        return super().has_permission(request, view)

class IsPremiumPlus(permissions.BasePermission):
    """
    Permite acesso apenas a usuários Premium Plus ou Superusers.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        # Checar campo plan no User (BD-001)
        if hasattr(request.user, 'plan'):
             return request.user.plan == 'PREMIUM_PLUS'
        return False
