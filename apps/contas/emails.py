import re

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags

ESCOLA_NOME = 'Colégio Estadual de Tempo Integral Paulo José de Oliveira'


def _html_para_texto(html_content):
    texto = strip_tags(html_content)
    linhas = [linha.strip() for linha in texto.splitlines()]
    texto_limpo = '\n'.join(linha for linha in linhas if linha)
    return re.sub(r'\n{3,}', '\n\n', texto_limpo).strip()


def _enviar_email_html(assunto, destinatario, template_name, contexto):
    html_content = render_to_string(template_name, contexto)
    text_content = _html_para_texto(html_content)

    reply_to_padrao = getattr(settings, 'DEFAULT_REPLY_TO', None)
    reply_to = [reply_to_padrao] if reply_to_padrao else None

    mensagem = EmailMultiAlternatives(
        subject=assunto,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[destinatario],
        reply_to=reply_to,
    )
    mensagem.attach_alternative(html_content, 'text/html')
    return mensagem.send(fail_silently=False)


def construir_url_reset_senha(uid, token):
    base_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173').rstrip('/')
    return f'{base_url}/redefinir-senha?uid={uid}&token={token}'


def construir_url_frontend(caminho=''):
    base_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173').rstrip('/')
    caminho_limpo = caminho.lstrip('/')
    return f'{base_url}/{caminho_limpo}' if caminho_limpo else base_url


def enviar_email_reset_senha(user, uid, token, perfil=None):
    """Envia e-mail HTML com link, uid e token para redefinição de senha."""
    destinatario = (perfil.email if perfil and perfil.email else user.email)
    nome = (
        perfil.nome
        if perfil and perfil.nome
        else (user.get_full_name() or user.username or destinatario)
    )
    timeout_segundos = getattr(settings, 'PASSWORD_RESET_TIMEOUT', 259200)
    expiracao_horas = max(1, int(timeout_segundos // 3600))

    contexto = {
        'nome': nome,
        'email': destinatario,
        'uid': uid,
        'token': token,
        'reset_url': construir_url_reset_senha(uid, token),
        'solicitado_em': timezone.now(),
        'expiracao_horas': expiracao_horas,
        'escola_nome': ESCOLA_NOME,
    }
    return _enviar_email_html(
        assunto='[Arandu] Redefinição de senha da sua conta',
        destinatario=destinatario,
        template_name='emails/reset_senha.html',
        contexto=contexto,
    )


def enviar_email_boas_vindas_aluno(perfil, senha_temporaria=None):
    """Envia e-mail HTML de boas-vindas ao aluno recém-cadastrado."""
    contexto = {
        'perfil': perfil,
        'senha_temporaria': senha_temporaria,
        'login_url': construir_url_frontend('login'),
        'cadastrado_em': perfil.criado_em or timezone.now(),
        'escola_nome': ESCOLA_NOME,
    }
    return _enviar_email_html(
        assunto='[Arandu] Bem-vindo(a) à Biblioteca Virtual Escolar!',
        destinatario=perfil.email,
        template_name='emails/boas_vindas_aluno.html',
        contexto=contexto,
    )


def enviar_email_confirmacao_emprestimo(emprestimo):
    """Envia e-mail HTML de confirmação de empréstimo digital (usado no Épico 4)."""
    contexto = {
        'emprestimo': emprestimo,
        'perfil': emprestimo.usuario,
        'livro': emprestimo.livro,
        'meus_emprestimos_url': construir_url_frontend('meus-emprestimos'),
        'escola_nome': ESCOLA_NOME,
    }
    return _enviar_email_html(
        assunto=f'[Arandu] Empréstimo confirmado: {emprestimo.livro.titulo}',
        destinatario=emprestimo.usuario.email,
        template_name='emails/confirmacao_emprestimo.html',
        contexto=contexto,
    )
