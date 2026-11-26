import secrets
import string

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from .emails import enviar_email_boas_vindas_aluno
from .models import PerfilUsuario
from .validators import validar_matricula

User = get_user_model()

_SIMBOLOS_SEGUROS = '@#$%&*!'
_LETRAS_MAIUSCULAS = 'ABCDEFGHJKLMNPQRSTUVWXYZ'
_LETRAS_MINUSCULAS = 'abcdefghijkmnopqrstuvwxyz'
_DIGITOS = '23456789'


def gerar_senha_temporaria(tamanho=10):
    """Gera senha temporária criptograficamente segura compatível com AUTH_PASSWORD_VALIDATORS."""
    tamanho_efetivo = max(tamanho, 8)
    obrigatorios = [
        secrets.choice(_LETRAS_MAIUSCULAS),
        secrets.choice(_LETRAS_MAIUSCULAS),
        secrets.choice(_LETRAS_MINUSCULAS),
        secrets.choice(_LETRAS_MINUSCULAS),
        secrets.choice(_DIGITOS),
        secrets.choice(_DIGITOS),
        secrets.choice(_SIMBOLOS_SEGUROS),
    ]
    alfabeto = _LETRAS_MAIUSCULAS + _LETRAS_MINUSCULAS + _DIGITOS + _SIMBOLOS_SEGUROS
    restantes = [secrets.choice(alfabeto) for _ in range(tamanho_efetivo - len(obrigatorios))]
    caracteres = obrigatorios + restantes
    secrets.SystemRandom().shuffle(caracteres)
    return ''.join(caracteres)


def _dividir_nome(nome_completo):
    partes = nome_completo.strip().split()
    if not partes:
        return '', ''
    first_name = partes[0][:150]
    last_name = ' '.join(partes[1:])[:150]
    return first_name, last_name


def _gerar_username_unico(email, matricula):
    candidatos = [email[:150], matricula[:150]]
    for candidato in candidatos:
        if candidato and not User.objects.filter(username__iexact=candidato).exists():
            return candidato

    base = (matricula or email.split('@')[0] or 'aluno')[:130]
    for _tentativa in range(20):
        sufixo = ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(6))
        candidato = f'{base}_{sufixo}'[:150]
        if not User.objects.filter(username__iexact=candidato).exists():
            return candidato

    return f'aluno_{secrets.token_hex(8)}'


def _enviar_boas_vindas_pos_commit(perfil_id, senha_temporaria=None):
    perfil = PerfilUsuario.objects.select_related('turma').filter(pk=perfil_id).first()
    if perfil is not None:
        enviar_email_boas_vindas_aluno(perfil, senha_temporaria=senha_temporaria)


def _validar_senha_para_usuario(senha, user_obj):
    try:
        validate_password(senha, user=user_obj)
    except DjangoValidationError as exc:
        raise DjangoValidationError({'senha': list(exc.messages)})


@transaction.atomic
def criar_aluno(
    *,
    nome,
    email,
    matricula,
    turma=None,
    telefone=None,
    ativo=True,
    senha=None,
    precisa_trocar_senha=True,
    enviar_email=True,
):
    """
    Cria User + PerfilUsuario(ALUNO) atomicamente.

    Se `senha` não for informada, gera uma senha temporária segura, força
    `precisa_trocar_senha=True` e agenda o e-mail de boas-vindas via `transaction.on_commit()`.
    Retorna a tupla `(perfil, senha_temporaria)` — `senha_temporaria` é preenchida apenas
    quando gerada automaticamente pelo sistema.
    """
    nome_limpo = (nome or '').strip()
    email_limpo = (email or '').strip().lower()
    matricula_limpa = (matricula or '').strip()
    telefone_limpo = telefone.strip() if isinstance(telefone, str) and telefone.strip() else None

    erros = {}
    if not nome_limpo:
        erros['nome'] = [_('O nome completo é obrigatório.')]
    if not email_limpo:
        erros['email'] = [_('O e-mail é obrigatório.')]
    if not matricula_limpa:
        erros['matricula'] = [_('A matrícula é obrigatória.')]
    else:
        try:
            validar_matricula(matricula_limpa)
        except DjangoValidationError as exc:
            erros['matricula'] = list(exc.messages)

    if email_limpo and (
        PerfilUsuario.objects.filter(email__iexact=email_limpo).exists()
        or User.objects.filter(email__iexact=email_limpo).exists()
    ):
        erros['email'] = [_('Já existe uma conta cadastrada com este e-mail.')]

    if matricula_limpa and PerfilUsuario.objects.filter(matricula__iexact=matricula_limpa).exists():
        erros['matricula'] = [_('Já existe um usuário cadastrado com esta matrícula.')]

    if erros:
        raise DjangoValidationError(erros)

    first_name, last_name = _dividir_nome(nome_limpo)
    username = _gerar_username_unico(email_limpo, matricula_limpa)

    senha_temporaria = None
    if senha:
        usuario_previo = User(
            username=username,
            email=email_limpo,
            first_name=first_name,
            last_name=last_name,
        )
        _validar_senha_para_usuario(senha, usuario_previo)
        senha_final = senha
    else:
        senha_temporaria = gerar_senha_temporaria(10)
        senha_final = senha_temporaria
        precisa_trocar_senha = True

    user = User.objects.create_user(
        username=username,
        email=email_limpo,
        password=senha_final,
        first_name=first_name,
        last_name=last_name,
        is_active=bool(ativo),
        is_staff=False,
        is_superuser=False,
    )

    perfil = PerfilUsuario.objects.create(
        user=user,
        nome=nome_limpo,
        email=email_limpo,
        matricula=matricula_limpa,
        tipo=PerfilUsuario.TIPO_ALUNO,
        turma=turma,
        telefone=telefone_limpo,
        ativo=bool(ativo),
        precisa_trocar_senha=bool(precisa_trocar_senha),
    )

    if enviar_email:
        perfil_id = perfil.id
        senha_email = senha_temporaria
        transaction.on_commit(
            lambda: _enviar_boas_vindas_pos_commit(perfil_id, senha_temporaria=senha_email)
        )

    return perfil, senha_temporaria


@transaction.atomic
def atualizar_aluno(perfil, **dados):
    """
    Atualiza PerfilUsuario(ALUNO) e sincroniza o User vinculado dentro de transação ACID.

    Bloqueia o registro de PerfilUsuario e depois o User (sem JOIN em FK anulável)
    para evitar condições de corrida no PostgreSQL.
    """
    perfil_travado = PerfilUsuario.objects.select_for_update().get(pk=perfil.pk)
    user_travado = (
        User.objects.select_for_update().get(pk=perfil_travado.user_id)
        if perfil_travado.user_id
        else None
    )

    email_anterior = perfil_travado.email
    erros = {}

    if 'nome' in dados:
        nome_limpo = (dados['nome'] or '').strip()
        if not nome_limpo:
            erros['nome'] = [_('O nome completo não pode ficar em branco.')]
        else:
            perfil_travado.nome = nome_limpo

    if 'email' in dados:
        email_limpo = (dados['email'] or '').strip().lower()
        if not email_limpo:
            erros['email'] = [_('O e-mail não pode ficar em branco.')]
        else:
            email_em_uso_perfil = (
                PerfilUsuario.objects.filter(email__iexact=email_limpo)
                .exclude(pk=perfil_travado.pk)
                .exists()
            )
            qs_user = User.objects.filter(email__iexact=email_limpo)
            if user_travado is not None:
                qs_user = qs_user.exclude(pk=user_travado.pk)
            if email_em_uso_perfil or qs_user.exists():
                erros['email'] = [_('Já existe uma conta cadastrada com este e-mail.')]
            else:
                perfil_travado.email = email_limpo

    if 'matricula' in dados:
        matricula_limpa = (dados['matricula'] or '').strip()
        if not matricula_limpa:
            erros['matricula'] = [_('A matrícula não pode ficar em branco.')]
        else:
            try:
                validar_matricula(matricula_limpa)
            except DjangoValidationError as exc:
                erros['matricula'] = list(exc.messages)
            else:
                if (
                    PerfilUsuario.objects.filter(matricula__iexact=matricula_limpa)
                    .exclude(pk=perfil_travado.pk)
                    .exists()
                ):
                    erros['matricula'] = [_('Já existe um usuário cadastrado com esta matrícula.')]
                else:
                    perfil_travado.matricula = matricula_limpa

    if 'turma' in dados:
        perfil_travado.turma = dados['turma']

    if 'telefone' in dados:
        telefone = dados['telefone']
        perfil_travado.telefone = (
            telefone.strip() if isinstance(telefone, str) and telefone.strip() else None
        )

    if 'ativo' in dados:
        perfil_travado.ativo = bool(dados['ativo'])

    if 'precisa_trocar_senha' in dados:
        perfil_travado.precisa_trocar_senha = bool(dados['precisa_trocar_senha'])

    if erros:
        raise DjangoValidationError(erros)

    nova_senha = dados.get('senha')
    if user_travado is not None:
        first_name, last_name = _dividir_nome(perfil_travado.nome)
        user_travado.first_name = first_name
        user_travado.last_name = last_name
        user_travado.email = perfil_travado.email
        user_travado.is_active = perfil_travado.ativo

        if (
            email_anterior
            and perfil_travado.email != email_anterior
            and user_travado.username.lower() == email_anterior.lower()
            and not User.objects.filter(username__iexact=perfil_travado.email)
            .exclude(pk=user_travado.pk)
            .exists()
        ):
            user_travado.username = perfil_travado.email[:150]

        if nova_senha:
            _validar_senha_para_usuario(nova_senha, user_travado)
            user_travado.set_password(nova_senha)

        user_travado.save()

    perfil_travado.save()
    return PerfilUsuario.objects.select_related('turma', 'user').get(pk=perfil_travado.pk)


@transaction.atomic
def desativar_aluno(perfil):
    """Desativa atomicamente o PerfilUsuario e o User vinculado."""
    return atualizar_aluno(perfil, ativo=False)
