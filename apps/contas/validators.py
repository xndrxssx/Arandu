import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

MATRICULA_REGEX = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{3,29}$')


def validar_matricula(valor):
    """Valida formato de matrícula institucional (4 a 30 caracteres alfanuméricos, '.', '_' ou '-')."""
    if not valor:
        return

    matricula = str(valor).strip()
    if not MATRICULA_REGEX.match(matricula):
        raise ValidationError(
            _(
                'Matrícula inválida. Use de 4 a 30 caracteres contendo apenas '
                'letras, números, hífen (-), ponto (.) ou sublinhado (_), '
                'iniciando por letra ou número.'
            )
        )
