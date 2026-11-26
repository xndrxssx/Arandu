from django.core.exceptions import ObjectDoesNotExist
from django.utils.translation import gettext_lazy as _
from rest_framework.permissions import BasePermission


def obter_perfil_usuario(user):
    """Retorna o PerfilUsuario associado ao User ou None se não existir."""
    if not user or not getattr(user, 'is_authenticated', False):
        return None
    try:
        return user.perfil
    except ObjectDoesNotExist:
        return None


class IsUsuarioAtivo(BasePermission):
    """Permite acesso apenas a usuários autenticados com User e PerfilUsuario ativos."""

    message = _('Sua conta está inativa ou não possui perfil ativo no sistema.')

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated or not user.is_active:
            return False

        perfil = obter_perfil_usuario(user)
        if perfil is not None:
            return bool(perfil.ativo)

        # Fallback apenas para administradores/staff criados via Django Admin/CLI
        return bool(user.is_staff or user.is_superuser)


class IsBibliotecario(BasePermission):
    """Restringe acesso a bibliotecários/gestores escolares ativos (ou staff/superuser)."""

    message = _('Acesso restrito a bibliotecários e administradores.')

    def has_permission(self, request, view):
        if not IsUsuarioAtivo().has_permission(request, view):
            return False

        user = request.user
        if user.is_superuser or user.is_staff:
            return True

        perfil = obter_perfil_usuario(user)
        return bool(perfil and perfil.eh_bibliotecario)
