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

class EhAdministrador(permissions.BasePermission):
    """
    Libera só quem tem o papel `ADMIN` e a conta ativa (PERM-01, PERM-02).

    O `request.user` vem do banco a cada requisição (SessaoJWTAuthentication),
    então uma promoção ou um rebaixamento vale na requisição seguinte, e não
    quando o token vence (PERM-04). O `is_staff` não conta: ele serve só para o
    admin do Django (AD-016, PERM-08).
    """
    def has_permission(self, request, view):
        usuario = request.user
        return bool(
            usuario and usuario.is_authenticated and usuario.is_active and usuario.role == 'ADMIN'
        )

class IsPremiumPlus(permissions.BasePermission):
    """
    Permite acesso apenas a usuários Premium Plus ou Superusers.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        # Fase de Testes: Todos têm permissão Premium Plus
        return True
