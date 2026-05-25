from rest_framework import permissions


class IsPremium(permissions.BasePermission):
    """
    Durante a fase de testes, libera recursos Premium para qualquer usuario autenticado.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        return True
