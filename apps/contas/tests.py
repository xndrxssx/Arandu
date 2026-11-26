from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.cache import cache
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APITestCase

from apps.arandu.models import Categoria, Emprestimo, Livro
from apps.contas.emails import enviar_email_confirmacao_emprestimo
from apps.contas.models import PerfilUsuario, Turma
from apps.contas.services import criar_aluno

User = get_user_model()


class Epico2BaseMixin:
    def setUp(self):
        super().setUp()
        cache.clear()
        mail.outbox.clear()

        self.turma_3a = Turma.objects.create(
            nome='3º Ano A',
            turno=Turma.TURNO_INTEGRAL,
            ano_letivo=2026,
            ativa=True,
        )
        self.turma_2b = Turma.objects.create(
            nome='2º Ano B',
            turno=Turma.TURNO_MANHA,
            ano_letivo=2026,
            ativa=True,
        )

        self.bib_password = 'Bib@2026Seguro'
        self.bib_user = User.objects.create_user(
            username='carlos.bib@arandu.edu.br',
            email='carlos.bib@arandu.edu.br',
            password=self.bib_password,
            first_name='Carlos',
            last_name='Bibliotecário',
            is_active=True,
        )
        self.bib_perfil = PerfilUsuario.objects.create(
            user=self.bib_user,
            nome='Carlos Bibliotecário',
            email='carlos.bib@arandu.edu.br',
            matricula='BIB-2026-01',
            tipo=PerfilUsuario.TIPO_BIBLIOTECARIO,
            ativo=True,
        )

        self.aluno_password = 'Aluno@2026Seguro'
        self.aluno_user = User.objects.create_user(
            username='ana.silva@arandu.edu.br',
            email='ana.silva@arandu.edu.br',
            password=self.aluno_password,
            first_name='Ana',
            last_name='Silva',
            is_active=True,
        )
        self.aluno_perfil = PerfilUsuario.objects.create(
            user=self.aluno_user,
            nome='Ana Clara Silva',
            email='ana.silva@arandu.edu.br',
            matricula='2026-00101',
            tipo=PerfilUsuario.TIPO_ALUNO,
            turma=self.turma_3a,
            telefone='(81) 99999-1111',
            ativo=True,
            precisa_trocar_senha=False,
        )

    def autenticar_como(self, identificador, password):
        resp = self.client.post(
            reverse('auth-login'),
            {'identificador': identificador, 'password': password},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data['access']}")
        return resp.data


class AutenticacaoJWTPermissoesTests(Epico2BaseMixin, APITestCase):
    """Testes da task T2.1 — Login JWT (e-mail ou matrícula), refresh, /me/ e permissões."""

    def test_login_com_email_sucesso(self):
        resp = self.client.post(
            reverse('auth-login'),
            {'identificador': '  ANA.SILVA@ARANDU.EDU.BR ', 'password': self.aluno_password},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('access', resp.data)
        self.assertIn('refresh', resp.data)
        self.assertEqual(resp.data['usuario']['matricula'], '2026-00101')
        self.assertEqual(resp.data['usuario']['tipo'], PerfilUsuario.TIPO_ALUNO)
        self.assertFalse(resp.data['usuario']['eh_bibliotecario'])
        self.assertEqual(resp.data['usuario']['turma']['nome'], '3º Ano A')

    def test_login_com_matricula_sucesso(self):
        resp = self.client.post(
            reverse('auth-login'),
            {'identificador': '2026-00101', 'password': self.aluno_password},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['usuario']['email'], 'ana.silva@arandu.edu.br')

    def test_login_senha_incorreta_retorna_401(self):
        resp = self.client.post(
            reverse('auth-login'),
            {'identificador': '2026-00101', 'password': 'SenhaErrada!99'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_conta_user_inativo_retorna_403(self):
        self.aluno_user.is_active = False
        self.aluno_user.save(update_fields=['is_active'])

        resp = self.client.post(
            reverse('auth-login'),
            {'identificador': '2026-00101', 'password': self.aluno_password},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_login_conta_perfil_inativo_retorna_403(self):
        self.aluno_perfil.ativo = False
        self.aluno_perfil.save(update_fields=['ativo'])

        resp = self.client.post(
            reverse('auth-login'),
            {'identificador': 'ana.silva@arandu.edu.br', 'password': self.aluno_password},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_refresh_token_ativo_e_bloqueio_apos_desativacao(self):
        tokens = self.autenticar_como('2026-00101', self.aluno_password)

        resp_ok = self.client.post(
            reverse('auth-refresh'),
            {'refresh': tokens['refresh']},
            format='json',
        )
        self.assertEqual(resp_ok.status_code, status.HTTP_200_OK)
        self.assertIn('access', resp_ok.data)

        # Desativa perfil e verifica que o refresh passa a ser recusado
        self.aluno_perfil.ativo = False
        self.aluno_perfil.save(update_fields=['ativo'])

        resp_blocked = self.client.post(
            reverse('auth-refresh'),
            {'refresh': tokens['refresh']},
            format='json',
        )
        self.assertEqual(resp_blocked.status_code, status.HTTP_403_FORBIDDEN)

    def test_me_retorna_perfil_turma_e_resumo_emprestimos(self):
        categoria = Categoria.objects.create(nome='Literatura Brasileira')
        livro_1 = Livro.objects.create(
            titulo='Dom Casmurro',
            categoria=categoria,
            ano_publicacao=1899,
            quantidade_total=3,
            quantidade_disponivel=2,
            dominio_publico=True,
        )
        livro_2 = Livro.objects.create(
            titulo='Vidas Secas',
            categoria=categoria,
            ano_publicacao=1938,
            quantidade_total=2,
            quantidade_disponivel=1,
            dominio_publico=False,
        )
        livro_3 = Livro.objects.create(
            titulo='O Cortiço',
            categoria=categoria,
            ano_publicacao=1890,
            quantidade_total=2,
            quantidade_disponivel=2,
            dominio_publico=True,
        )

        hoje = timezone.localdate()
        Emprestimo.objects.create(
            usuario=self.aluno_perfil,
            livro=livro_1,
            data_prevista_devolucao=hoje + timedelta(days=7),
            status=Emprestimo.STATUS_ATIVO,
        )
        Emprestimo.objects.create(
            usuario=self.aluno_perfil,
            livro=livro_2,
            data_prevista_devolucao=hoje - timedelta(days=2),
            status=Emprestimo.STATUS_ATRASADO,
        )
        Emprestimo.objects.create(
            usuario=self.aluno_perfil,
            livro=livro_3,
            data_prevista_devolucao=hoje - timedelta(days=10),
            data_devolucao=timezone.now() - timedelta(days=9),
            status=Emprestimo.STATUS_DEVOLVIDO,
        )

        self.autenticar_como('2026-00101', self.aluno_password)
        resp = self.client.get(reverse('auth-me'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['nome'], 'Ana Clara Silva')
        self.assertEqual(resp.data['turma']['nome'], '3º Ano A')
        self.assertEqual(
            resp.data['resumo_emprestimos'],
            {'ativos': 1, 'atrasados': 1, 'devolvidos': 1, 'total': 3},
        )

    def test_aluno_recebe_403_em_endpoints_gestao(self):
        self.autenticar_como('2026-00101', self.aluno_password)

        resp_alunos = self.client.get(reverse('gestao-alunos-list'))
        resp_turmas = self.client.get(reverse('gestao-turmas-list'))
        self.assertEqual(resp_alunos.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp_turmas.status_code, status.HTTP_403_FORBIDDEN)


class RecuperacaoSenhaEmailsTests(Epico2BaseMixin, APITestCase):
    """Testes da task T2.2 — Esqueci senha, redefinir senha e templates HTML com humanize."""

    def test_fluxo_completo_esqueci_e_redefinir_senha(self):
        self.aluno_perfil.precisa_trocar_senha = True
        self.aluno_perfil.save(update_fields=['precisa_trocar_senha'])

        resp_esqueci = self.client.post(
            reverse('auth-esqueci-senha'),
            {'email': 'ANA.SILVA@ARANDU.EDU.BR'},
            format='json',
        )
        self.assertEqual(resp_esqueci.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)

        email_enviado = mail.outbox[0]
        self.assertEqual(email_enviado.to, ['ana.silva@arandu.edu.br'])
        self.assertEqual(len(email_enviado.alternatives), 1)
        html_body, mimetype = email_enviado.alternatives[0]
        self.assertEqual(mimetype, 'text/html')

        uid = urlsafe_base64_encode(force_bytes(self.aluno_user.pk))
        self.assertIn(uid, html_body)

        # Extrai token do link gerado no corpo do e-mail
        token_parte = html_body.split('token=')[1].split('"')[0]

        nova_senha = 'NovaSenha@2026!'
        resp_reset = self.client.post(
            reverse('auth-redefinir-senha'),
            {
                'uid': uid,
                'token': token_parte,
                'nova_senha': nova_senha,
                'confirmar_nova_senha': nova_senha,
            },
            format='json',
        )
        self.assertEqual(resp_reset.status_code, status.HTTP_200_OK)

        # Flag precisa_trocar_senha deve ser limpa após redefinição
        self.aluno_perfil.refresh_from_db()
        self.assertFalse(self.aluno_perfil.precisa_trocar_senha)

        # Login funciona com a nova senha
        resp_login = self.client.post(
            reverse('auth-login'),
            {'identificador': '2026-00101', 'password': nova_senha},
            format='json',
        )
        self.assertEqual(resp_login.status_code, status.HTTP_200_OK)

        # Reutilizar o mesmo token deve falhar com 400
        resp_reuso = self.client.post(
            reverse('auth-redefinir-senha'),
            {
                'uid': uid,
                'token': token_parte,
                'nova_senha': 'OutraSenha@2026!',
            },
            format='json',
        )
        self.assertEqual(resp_reuso.status_code, status.HTTP_400_BAD_REQUEST)

    def test_esqueci_senha_email_inexistente_retorna_200_sem_enviar(self):
        resp = self.client.post(
            reverse('auth-esqueci-senha'),
            {'email': 'nao.existe@arandu.edu.br'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 0)

    def test_redefinir_senha_rejeita_senha_fraca_e_token_invalido(self):
        uid = urlsafe_base64_encode(force_bytes(self.aluno_user.pk))
        token = default_token_generator.make_token(self.aluno_user)

        # Senha puramente numérica deve falhar nos AUTH_PASSWORD_VALIDATORS
        resp_fraca = self.client.post(
            reverse('auth-redefinir-senha'),
            {'uid': uid, 'token': token, 'nova_senha': '12345678'},
            format='json',
        )
        self.assertEqual(resp_fraca.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('nova_senha', resp_fraca.data)

        # Token inválido deve falhar
        resp_token_invalido = self.client.post(
            reverse('auth-redefinir-senha'),
            {'uid': uid, 'token': 'token-forjado-invalido', 'nova_senha': 'Forte@2026!'},
            format='json',
        )
        self.assertEqual(resp_token_invalido.status_code, status.HTTP_400_BAD_REQUEST)

    def test_template_confirmacao_emprestimo_renderiza_com_humanize(self):
        categoria = Categoria.objects.create(nome='História')
        livro = Livro.objects.create(
            titulo='Casa-Grande & Senzala',
            categoria=categoria,
            ano_publicacao=1933,
            quantidade_total=2,
            quantidade_disponivel=1,
            dominio_publico=False,
        )
        emprestimo = Emprestimo.objects.create(
            usuario=self.aluno_perfil,
            livro=livro,
            data_prevista_devolucao=timezone.localdate() + timedelta(days=7),
            status=Emprestimo.STATUS_ATIVO,
        )

        enviar_email_confirmacao_emprestimo(emprestimo)
        self.assertEqual(len(mail.outbox), 1)
        html_body, _ = mail.outbox[0].alternatives[0]
        self.assertIn('Casa-Grande &amp; Senzala', html_body)
        self.assertIn('Leitura exclusiva na plataforma', html_body)


class GestaoAlunosTurmasTests(Epico2BaseMixin, APITestCase):
    """Testes da task T2.3 — Gestão transacional ACID de alunos e turmas pelo bibliotecário."""

    def test_criar_aluno_sem_senha_gera_temporaria_e_envia_email_no_commit(self):
        self.autenticar_como('BIB-2026-01', self.bib_password)

        payload = {
            'nome': 'João Pedro Santos',
            'email': 'joao.santos@arandu.edu.br',
            'matricula': '2026-00202',
            'turma': str(self.turma_2b.id),
            'telefone': '(81) 98888-2222',
        }

        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client.post(reverse('gestao-alunos-list'), payload, format='json')

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertIn('senha_temporaria', resp.data)
        senha_temp = resp.data['senha_temporaria']
        self.assertIsNotNone(senha_temp)
        self.assertGreaterEqual(len(senha_temp), 8)
        self.assertTrue(resp.data['precisa_trocar_senha'])
        self.assertEqual(resp.data['turma_detalhes']['nome'], '2º Ano B')

        # E-mail de boas-vindas disparado após commit com a senha temporária
        self.assertEqual(len(mail.outbox), 1)
        html_body, _ = mail.outbox[0].alternatives[0]
        self.assertIn(senha_temp, html_body)
        self.assertIn('2026-00202', html_body)

        # GET subsequente nunca expõe senha_temporaria
        resp_detalhe = self.client.get(reverse('gestao-alunos-detail', args=[resp.data['id']]))
        self.assertEqual(resp_detalhe.status_code, status.HTTP_200_OK)
        self.assertNotIn('senha_temporaria', resp_detalhe.data)

        # Aluno recém-criado consegue fazer login imediatamente com a senha temporária
        self.client.credentials()
        resp_login = self.client.post(
            reverse('auth-login'),
            {'identificador': '2026-00202', 'password': senha_temp},
            format='json',
        )
        self.assertEqual(resp_login.status_code, status.HTTP_200_OK)

    def test_rollback_nao_dispara_email_nem_persiste_usuario(self):
        with self.assertRaises(RuntimeError):
            with self.captureOnCommitCallbacks(execute=True):
                with transaction.atomic():
                    criar_aluno(
                        nome='Aluno Rollback',
                        email='rollback@arandu.edu.br',
                        matricula='2026-09999',
                        turma=self.turma_3a,
                    )
                    raise RuntimeError('Falha simulada após criação')

        self.assertFalse(User.objects.filter(email='rollback@arandu.edu.br').exists())
        self.assertFalse(PerfilUsuario.objects.filter(matricula='2026-09999').exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_desativar_aluno_via_patch_bloqueia_login_e_me_imediatamente(self):
        # Aluno faz login enquanto ativo
        tokens_aluno = self.autenticar_como('2026-00101', self.aluno_password)

        # Bibliotecário desativa o aluno via PATCH
        self.autenticar_como('BIB-2026-01', self.bib_password)
        resp_patch = self.client.patch(
            reverse('gestao-alunos-detail', args=[self.aluno_perfil.id]),
            {'ativo': False, 'nome': 'Ana Clara Silva Atualizada'},
            format='json',
        )
        self.assertEqual(resp_patch.status_code, status.HTTP_200_OK)
        self.assertFalse(resp_patch.data['ativo'])

        self.aluno_user.refresh_from_db()
        self.aluno_perfil.refresh_from_db()
        self.assertFalse(self.aluno_user.is_active)
        self.assertFalse(self.aluno_perfil.ativo)
        self.assertEqual(self.aluno_user.first_name, 'Ana')
        self.assertEqual(self.aluno_user.last_name, 'Clara Silva Atualizada')

        # Token antigo do aluno já é bloqueado no /me/ (SimpleJWT retorna 401 pois user.is_active=False)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens_aluno['access']}")
        resp_me = self.client.get(reverse('auth-me'))
        self.assertEqual(resp_me.status_code, status.HTTP_401_UNAUTHORIZED)

        # Novo login é bloqueado imediatamente
        self.client.credentials()
        resp_login = self.client.post(
            reverse('auth-login'),
            {'identificador': '2026-00101', 'password': self.aluno_password},
            format='json',
        )
        self.assertEqual(resp_login.status_code, status.HTTP_403_FORBIDDEN)

    def test_perfil_inativo_com_user_ativo_bloqueado_por_is_usuario_ativo(self):
        tokens_aluno = self.autenticar_como('2026-00101', self.aluno_password)

        self.aluno_perfil.ativo = False
        self.aluno_perfil.save(update_fields=['ativo'])

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens_aluno['access']}")
        resp_me = self.client.get(reverse('auth-me'))
        self.assertEqual(resp_me.status_code, status.HTTP_403_FORBIDDEN)

    def test_listar_e_buscar_alunos_paginado(self):
        self.autenticar_como('BIB-2026-01', self.bib_password)

        resp = self.client.get(reverse('gestao-alunos-list'), {'search': '3º Ano A'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('count', resp.data)
        self.assertIn('total_pages', resp.data)
        self.assertIn('current_page', resp.data)
        self.assertIn('results', resp.data)
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['results'][0]['matricula'], '2026-00101')

        # Busca por matrícula
        resp_mat = self.client.get(reverse('gestao-alunos-list'), {'search': '2026-00101'})
        self.assertEqual(resp_mat.data['count'], 1)

    def test_crud_turmas_bibliotecario(self):
        self.autenticar_como('BIB-2026-01', self.bib_password)

        resp_create = self.client.post(
            reverse('gestao-turmas-list'),
            {'nome': '1º Ano C', 'turno': Turma.TURNO_TARDE, 'ano_letivo': 2026},
            format='json',
        )
        self.assertEqual(resp_create.status_code, status.HTTP_201_CREATED)
        turma_id = resp_create.data['id']
        self.assertEqual(resp_create.data['turno_display'], 'Tarde')

        # Duplicata de (nome, ano_letivo) deve retornar 400
        resp_dup = self.client.post(
            reverse('gestao-turmas-list'),
            {'nome': '1º Ano C', 'turno': Turma.TURNO_MANHA, 'ano_letivo': 2026},
            format='json',
        )
        self.assertEqual(resp_dup.status_code, status.HTTP_400_BAD_REQUEST)

        # Listagem paginada inclui total_alunos
        resp_list = self.client.get(reverse('gestao-turmas-list'))
        self.assertEqual(resp_list.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_list.data['count'], 3)

        # PATCH atualiza turma
        resp_patch = self.client.patch(
            reverse('gestao-turmas-detail', args=[turma_id]),
            {'ativa': False},
            format='json',
        )
        self.assertEqual(resp_patch.status_code, status.HTTP_200_OK)
        self.assertFalse(resp_patch.data['ativa'])

    def test_envio_email_erro_rollback_nao_afeta_teste_isolado(self):
        with patch('apps.contas.services.enviar_email_boas_vindas_aluno') as mock_email:
            with self.captureOnCommitCallbacks(execute=True):
                criar_aluno(
                    nome='Mariana Costa',
                    email='mariana.costa@arandu.edu.br',
                    matricula='2026-00303',
                    turma=self.turma_3a,
                    senha='SenhaManual@2026',
                )
            mock_email.assert_called_once()
            _, kwargs = mock_email.call_args
            self.assertIsNone(kwargs['senha_temporaria'])
