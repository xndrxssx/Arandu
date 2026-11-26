import os
import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

MAX_PDF_SIZE_MB = 25
MAX_PDF_SIZE_BYTES = MAX_PDF_SIZE_MB * 1024 * 1024
PDF_MAGIC_BYTES = b'%PDF-'


def validar_isbn(valor):
    """Valida códigos ISBN-10 e ISBN-13 (aceitando hífens e espaços)."""
    if not valor:
        return

    codigo = re.sub(r'[-\s]', '', str(valor)).upper()

    if len(codigo) == 10:
        if not re.match(r'^\d{9}[\dX]$', codigo):
            raise ValidationError(_('ISBN-10 inválido. Verifique os dígitos informados.'))
        total = sum(
            (10 - idx) * (10 if ch == 'X' else int(ch))
            for idx, ch in enumerate(codigo)
        )
        if total % 11 != 0:
            raise ValidationError(_('Dígito verificador do ISBN-10 é inválido.'))
        return

    if len(codigo) == 13:
        if not re.match(r'^(978|979)\d{10}$', codigo):
            raise ValidationError(_('ISBN-13 inválido. Deve iniciar com 978 ou 979 e conter 13 dígitos.'))
        total = sum(
            int(ch) * (1 if idx % 2 == 0 else 3)
            for idx, ch in enumerate(codigo)
        )
        if total % 10 != 0:
            raise ValidationError(_('Dígito verificador do ISBN-13 é inválido.'))
        return

    raise ValidationError(_('ISBN inválido. Informe um ISBN-10 ou ISBN-13 válido.'))


def validar_extensao_pdf(arquivo):
    """Garante que o arquivo possui extensão .pdf."""
    if not arquivo:
        return

    nome = getattr(arquivo, 'name', '') or ''
    extensao = os.path.splitext(nome)[1].lower()
    if extensao != '.pdf':
        raise ValidationError(_('Apenas arquivos com extensão .pdf são permitidos.'))


def validar_tamanho_pdf(arquivo):
    """Limita o tamanho máximo do PDF a 25 MB."""
    if not arquivo:
        return

    tamanho = getattr(arquivo, 'size', None)
    if tamanho is not None and tamanho > MAX_PDF_SIZE_BYTES:
        raise ValidationError(
            _('O arquivo PDF excede o limite máximo permitido de %(max_mb)d MB.'),
            params={'max_mb': MAX_PDF_SIZE_MB},
        )


def validar_magic_bytes_pdf(arquivo):
    """Valida a assinatura binária (%PDF-) para bloquear arquivos renomeados."""
    if not arquivo:
        return

    file_obj = getattr(arquivo, 'file', arquivo)
    deve_fechar = False
    pos_original = None

    try:
        if getattr(file_obj, 'closed', False):
            file_obj.open('rb')
            deve_fechar = True

        if hasattr(file_obj, 'tell'):
            try:
                pos_original = file_obj.tell()
            except (OSError, ValueError):
                pos_original = None

        if hasattr(file_obj, 'seek'):
            file_obj.seek(0)

        cabecalho = file_obj.read(len(PDF_MAGIC_BYTES))
    except OSError:
        raise ValidationError(_('Não foi possível ler o arquivo enviado para validar o formato PDF.'))
    finally:
        if pos_original is not None and hasattr(file_obj, 'seek') and not getattr(file_obj, 'closed', False):
            try:
                file_obj.seek(pos_original)
            except (OSError, ValueError):
                pass
        if deve_fechar and hasattr(file_obj, 'close'):
            file_obj.close()

    if isinstance(cabecalho, str):
        cabecalho = cabecalho.encode('latin-1', errors='ignore')

    if not cabecalho.startswith(PDF_MAGIC_BYTES):
        raise ValidationError(
            _('Arquivo inválido: o conteúdo não corresponde a um documento PDF legítimo (%PDF-).')
        )


def validar_arquivo_pdf(arquivo):
    """Executa validação completa de PDF: extensão, tamanho máximo (25 MB) e magic bytes."""
    if not arquivo:
        return

    validar_extensao_pdf(arquivo)
    validar_tamanho_pdf(arquivo)
    validar_magic_bytes_pdf(arquivo)


def validar_nota(valor):
    """Garante que a nota da avaliação esteja no intervalo de 1 a 5."""
    if valor is None:
        return

    if not isinstance(valor, int) or valor < 1 or valor > 5:
        raise ValidationError(_('A nota deve ser um número inteiro entre 1 e 5.'))
