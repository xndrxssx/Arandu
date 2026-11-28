import io
import shutil
import tempfile
import zipfile
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.arandu.models import (
    Autor,
    Avaliacao,
    Categoria,
    Editora,
    Emprestimo,
    Livro,
    RegistroAcesso,
)
from apps.arandu.storage import private_storage
from apps.arandu.validators import validar_arquivo_digital
from apps.contas.models import PerfilUsuario, Turma

User = get_user_model()


def _criar_pdf_valido(nome='obra.pdf'):
    conteudo = b'%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n'
    return SimpleUploadedFile(nome, conteudo, content_type='application/pdf')


def _criar_epub_valido(nome='obra.epub'):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as zf:
        zf.writestr('mimetype', 'application/epub+zip', compress_type=zipfile.ZIP_STORED)
        zf.writestr('META-INF/container.xml', '<container version="1.0"/>')
    return SimpleUploadedFile(nome, buffer.getvalue(), content_type='application/epub+zip')


def _criar_zip_sem_mimetype(nome='falso.epub'):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as zf:
        zf.writestr('readme.txt', 'nao sou epub')
    return SimpleUploadedFile(nome, buffer.getvalue(), content_type='application/epub+zip')


class CatalogoBaseMixin:
    def setUp(self):
        super().setUp()
        cache.clear()
        self._temp_private_dir = tempfile.mkdtemp(prefix='arandu_test_private_')
        self._original_private_location = private_storage.location
        private_storage.location = self._temp_private_dir
        if 'location' in private_storage.__dict__:
            private_storage.__dict__['location'] = self._temp_private_dir

        self.turma_3a = Turma.objects.create(
            nome='3º Ano A',
            turno=Turma.TURNO_INTEGRAL,
            ano_letivo=2026,
            ativa=True,
        )

        self.bib_password = 'Bib@2026Seguro'
        self.bib_user = User.objects.create_user(
            username='carlos.bib@arandu.edu.br',
            email='carlos.bib@arandu.edu.br',
            password=self.bib_password,
            is_active=True,
        )
        self.bib_perfil = PerfilUsuario.objects.create(
            user=self.bib_user,
            nome='Prof. Carlos Mendes',
            email='carlos.bib@arandu.edu.br',
            matricula='BIB-2026-10',
            tipo=PerfilUsuario.TIPO_BIBLIOTECARIO,
            ativo=True,
        )

        self.aluno_password = 'Aluno@2026Seguro'
        self.aluno_user = User.objects.create_user(
            username='maria.aluna@arandu.edu.br',
            email='maria.aluna@arandu.edu.br',
            password=self.aluno_password,
            is_active=True,
        )
        self.aluno_perfil = PerfilUsuario.objects.create(
            user=self.aluno_user,
            nome='Maria Eduarda',
            email='maria.aluna@arandu.edu.br',
            matricula='2026-01001',
            tipo=PerfilUsuario.TIPO_ALUNO,
            turma=self.turma_3a,
            ativo=True,
        )

        self.outro_aluno_user = User.objects.create_user(
            username='joao.aluno@arandu.edu.br',
            email='joao.aluno@arandu.edu.br',
            password=self.aluno_password,
            is_active=True,
        )
        self.outro_aluno_perfil = PerfilUsuario.objects.create(
            user=self.outro_aluno_user,
            nome='João Pedro',
            email='joao.aluno@arandu.edu.br',
            matricula='2026-01002',
            tipo=PerfilUsuario.TIPO_ALUNO,
            turma=self.turma_3a,
            ativo=True,
        )

        self.cat_lit = Categoria.objects.create(
            nome='Literatura Brasileira',
            descricao='Clássicos e autores nacionais.',
        )
        self.cat_mat = Categoria.objects.create(
            nome='Matemática',
            descricao='Apostilas e exercícios de revisão.',
        )

        self.autor_machado = Autor.objects.create(
            nome='Machado de Assis',
            nacionalidade='Brasileira',
        )
        self.autor_graciliano = Autor.objects.create(
            nome='Graciliano Ramos',
            nacionalidade='Brasileira',
        )
        self.autor_colaborador = Autor.objects.create(
            nome='Coordenação de Matemática',
            nacionalidade='Brasileira',
        )

        self.editora_escola = Editora.objects.create(
            nome='Acervo CETI PJO',
            cidade='Recife',
        )

        # Obra 1: Domínio Público em PDF
        self.livro_dp_pdf = Livro.objects.create(
            titulo='Dom Casmurro',
            categoria=self.cat_lit,
            editora=self.editora_escola,
            isbn='978-85-359-0277-8',
            ano_publicacao=1899,
            sinopse='Narrativa clássica de Bentinho e Capitu.',
            arquivo_pdf=_criar_pdf_valido('dom-casmurro.pdf'),
            quantidade_total=1,
            quantidade_disponivel=1,
            dominio_publico=True,
            ativo=True,
            cadastrado_por=self.bib_perfil,
        )
        self.livro_dp_pdf.autores.add(self.autor_machado)

        # Obra 2: Domínio Público em EPUB
        self.livro_dp_epub = Livro.objects.create(
            titulo='Memórias Póstumas de Brás Cubas',
            categoria=self.cat_lit,
            editora=self.editora_escola,
            ano_publicacao=1881,
            sinopse='Obra de domínio público em formato EPUB.',
            arquivo_pdf=_criar_epub_valido('bras-cubas.epub'),
            quantidade_total=1,
            quantidade_disponivel=1,
            dominio_publico=True,
            ativo=True,
            cadastrado_por=self.bib_perfil,
        )
        self.livro_dp_epub.autores.add(self.autor_machado)

        # Obra 3: Aluguel Temporário em PDF (disponível, 2 autores para testar distinct na busca)
        self.livro_aluguel = Livro.objects.create(
            titulo='Vidas Secas',
            categoria=self.cat_lit,
            editora=self.editora_escola,
            isbn='9788501012074',
            ano_publicacao=1938,
            sinopse='Retrato da seca no sertão nordestino.',
            arquivo_pdf=_criar_pdf_valido('vidas-secas.pdf'),
            quantidade_total=3,
            quantidade_disponivel=2,
            dominio_publico=False,
            ativo=True,
            cadastrado_por=self.bib_perfil,
        )
        self.livro_aluguel.autores.add(self.autor_graciliano, self.autor_colaborador)

        # Obra 4: Aluguel Temporário sem exemplares disponíveis
        self.livro_esgotado = Livro.objects.create(
            titulo='Caderno ENEM Matemática',
            categoria=self.cat_mat,
            ano_publicacao=2026,
            sinopse='Revisão completa de matemática.',
            arquivo_pdf=_criar_pdf_valido('enem-mat.pdf'),
            quantidade_total=1,
            quantidade_disponivel=0,
            dominio_publico=False,
            ativo=True,
            cadastrado_por=self.bib_perfil,
        )
        self.livro_esgotado.autores.add(self.autor_colaborador)

        # Obra 5: Oculta (ativo=False) — não deve aparecer no catálogo público/aluno
        self.livro_oculto = Livro.objects.create(
            titulo='Rascunho Interno',
            categoria=self.cat_mat,
            ano_publicacao=2026,
            quantidade_total=1,
            quantidade_disponivel=1,
            dominio_publico=True,
            ativo=False,
        )

    def tearDown(self):
        private_storage.location = self._original_private_location
        if 'location' in private_storage.__dict__:
            private_storage.__dict__['location'] = self._original_private_location
        shutil.rmtree(self._temp_private_dir, ignore_errors=True)
        super().tearDown()

    def autenticar_como(self, identificador, password):
        resp = self.client.post(
            reverse('auth-login'),
            {'identificador': identificador, 'password': password},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data['access']}")
        return resp.data


class ValidadoresERegraHibridaTests(CatalogoBaseMixin, APITestCase):
    """Valida a regra híbrida PDF/EPUB (domínio público aceita ambos; aluguel só PDF)."""

    def test_arquivo_txt_renomeado_para_pdf_eh_rejeitado(self):
        falso_pdf = SimpleUploadedFile('malware.pdf', b'texto comum disfarcado', content_type='application/pdf')
        with self.assertRaises(ValidationError):
            validar_arquivo_digital(falso_pdf)

    def test_zip_sem_mimetype_renomeado_para_epub_eh_rejeitado(self):
        with self.assertRaises(ValidationError):
            validar_arquivo_digital(_criar_zip_sem_mimetype())

    def test_epub_valido_em_dominio_publico_passa_e_detecta_formato(self):
        self.assertEqual(self.livro_dp_epub.formato, Livro.FORMATO_EPUB)
        self.assertTrue(self.livro_dp_epub.pode_baixar_direto)
        self.assertFalse(self.livro_dp_epub.pode_ler_online_direto)

    def test_epub_em_aluguel_temporario_eh_rejeitado_no_clean(self):
        livro_invalido = Livro(
            titulo='Aluguel em EPUB Inválido',
            categoria=self.cat_lit,
            ano_publicacao=2024,
            arquivo_pdf=_criar_epub_valido('aluguel.epub'),
            quantidade_total=2,
            quantidade_disponivel=2,
            dominio_publico=False,
            ativo=True,
        )
        with self.assertRaises(ValidationError) as ctx:
            livro_invalido.full_clean()
        self.assertIn('arquivo_pdf', ctx.exception.message_dict)


class CatalogoLivrosAPITests(CatalogoBaseMixin, APITestCase):
    """Testes da T3.1 — Catálogo paginado, filtros, busca, detalhes e zero N+1."""

    def test_catalogo_exige_autenticacao(self):
        resp = self.client.get(reverse('catalogo-livros-list'))
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_listagem_paginada_omite_inativos_e_nao_expoe_url_privada(self):
        self.autenticar_como('2026-01001', self.aluno_password)
        resp = self.client.get(reverse('catalogo-livros-list'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        # Envelope AranduPagination
        for chave in ('count', 'total_pages', 'current_page', 'next', 'previous', 'results'):
            self.assertIn(chave, resp.data)

        self.assertEqual(resp.data['count'], 4)
        titulos = [item['titulo'] for item in resp.data['results']]
        self.assertNotIn('Rascunho Interno', titulos)

        primeiro = resp.data['results'][0]
        self.assertNotIn('arquivo_pdf', primeiro)
        self.assertIn('nome_arquivo', primeiro)
        self.assertIn('tamanho_arquivo', primeiro)
        self.assertIn('formato', primeiro)
        self.assertTrue(primeiro['possui_arquivo'])
        self.assertNotIn('/', primeiro['nome_arquivo'])

    def test_busca_por_titulo_autor_e_isbn_sem_duplicar(self):
        self.autenticar_como('2026-01001', self.aluno_password)

        # Busca por autor compartilhado / múltiplos autores não duplica livro
        resp_autor = self.client.get(reverse('catalogo-livros-list'), {'search': 'Graciliano'})
        self.assertEqual(resp_autor.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_autor.data['count'], 1)
        self.assertEqual(resp_autor.data['results'][0]['titulo'], 'Vidas Secas')

        # Busca por ISBN
        resp_isbn = self.client.get(reverse('catalogo-livros-list'), {'search': '9788501012074'})
        self.assertEqual(resp_isbn.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_isbn.data['count'], 1)
        self.assertEqual(resp_isbn.data['results'][0]['titulo'], 'Vidas Secas')

    def test_filtros_categoria_slug_uuid_dominio_publico_disponivel_e_formato(self):
        self.autenticar_como('2026-01001', self.aluno_password)

        # Categoria por slug
        r_slug = self.client.get(reverse('catalogo-livros-list'), {'categoria': self.cat_mat.slug})
        self.assertEqual(r_slug.data['count'], 1)
        self.assertEqual(r_slug.data['results'][0]['titulo'], 'Caderno ENEM Matemática')

        # Categoria por UUID
        r_uuid = self.client.get(reverse('catalogo-livros-list'), {'categoria': str(self.cat_lit.id)})
        self.assertEqual(r_uuid.data['count'], 3)

        # Domínio público
        r_dp = self.client.get(reverse('catalogo-livros-list'), {'dominio_publico': 'true'})
        self.assertEqual(r_dp.data['count'], 2)

        # Disponível = false (apenas o esgotado em aluguel temporário)
        r_indisp = self.client.get(reverse('catalogo-livros-list'), {'disponivel': 'false'})
        self.assertEqual(r_indisp.data['count'], 1)
        self.assertEqual(r_indisp.data['results'][0]['titulo'], 'Caderno ENEM Matemática')

        # Formato = EPUB
        r_epub = self.client.get(reverse('catalogo-livros-list'), {'formato': 'epub'})
        self.assertEqual(r_epub.data['count'], 1)
        self.assertEqual(r_epub.data['results'][0]['titulo'], 'Memórias Póstumas de Brás Cubas')

    def test_agregacoes_nota_media_e_total_acessos_sem_distorcao_join(self):
        Avaliacao.objects.create(usuario=self.aluno_perfil, livro=self.livro_dp_pdf, nota=5, comentario='Excelente!')
        Avaliacao.objects.create(usuario=self.outro_aluno_perfil, livro=self.livro_dp_pdf, nota=3, comentario='Bom')
        for _ in range(3):
            RegistroAcesso.objects.create(
                usuario=self.aluno_perfil,
                livro=self.livro_dp_pdf,
                tipo=RegistroAcesso.TIPO_DOWNLOAD,
            )

        self.autenticar_como('2026-01001', self.aluno_password)
        resp = self.client.get(reverse('catalogo-livros-detail', args=[self.livro_dp_pdf.id]))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['nota_media'], 4.0)
        self.assertEqual(resp.data['total_avaliacoes'], 2)
        self.assertEqual(resp.data['total_acessos'], 3)
        self.assertEqual(resp.data['minha_avaliacao']['nota'], 5)
        self.assertEqual(resp.data['cadastrado_por_nome'], 'Prof. Carlos Mendes')

    def test_regras_pode_ler_e_pode_baixar_nos_detalhes(self):
        self.autenticar_como('2026-01001', self.aluno_password)

        # 1. Domínio Público PDF → pode_baixar=True e pode_ler=True sem empréstimo
        r_dp_pdf = self.client.get(reverse('catalogo-livros-detail', args=[self.livro_dp_pdf.id]))
        self.assertTrue(r_dp_pdf.data['pode_baixar'])
        self.assertTrue(r_dp_pdf.data['pode_ler'])

        # 2. Domínio Público EPUB → pode_baixar=True e pode_ler=False (leitor web só PDF)
        r_dp_epub = self.client.get(reverse('catalogo-livros-detail', args=[self.livro_dp_epub.id]))
        self.assertTrue(r_dp_epub.data['pode_baixar'])
        self.assertFalse(r_dp_epub.data['pode_ler'])

        # 3. Aluguel Temporário PDF sem empréstimo → ambos False
        r_aluguel_sem = self.client.get(reverse('catalogo-livros-detail', args=[self.livro_aluguel.id]))
        self.assertFalse(r_aluguel_sem.data['pode_baixar'])
        self.assertFalse(r_aluguel_sem.data['pode_ler'])
        self.assertIsNone(r_aluguel_sem.data['meu_emprestimo'])

        # 4. Aluguel Temporário PDF com empréstimo ATIVO → pode_ler=True, pode_baixar=False
        emprestimo = Emprestimo.objects.create(
            usuario=self.aluno_perfil,
            livro=self.livro_aluguel,
            data_prevista_devolucao=timezone.localdate() + timedelta(days=7),
            status=Emprestimo.STATUS_ATIVO,
        )
        r_aluguel_com = self.client.get(reverse('catalogo-livros-detail', args=[self.livro_aluguel.id]))
        self.assertFalse(r_aluguel_com.data['pode_baixar'])
        self.assertTrue(r_aluguel_com.data['pode_ler'])
        self.assertEqual(r_aluguel_com.data['meu_emprestimo']['id'], str(emprestimo.id))

        # 5. Bibliotecário pode ler aluguel temporário mesmo sem empréstimo
        self.autenticar_como('BIB-2026-10', self.bib_password)
        r_bib = self.client.get(reverse('catalogo-livros-detail', args=[self.livro_aluguel.id]))
        self.assertFalse(r_bib.data['pode_baixar'])
        self.assertTrue(r_bib.data['pode_ler'])

    def test_obra_inativa_retorna_404_nos_detalhes(self):
        self.autenticar_como('2026-01001', self.aluno_password)
        resp = self.client.get(reverse('catalogo-livros-detail', args=[self.livro_oculto.id]))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_listagem_catalogo_nao_faz_n_mais_1_queries(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        self.autenticar_como('2026-01001', self.aluno_password)

        with CaptureQueriesContext(connection) as ctx_inicial:
            resp_inicial = self.client.get(reverse('catalogo-livros-list'))
        self.assertEqual(resp_inicial.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp_inicial.data['results']), 4)

        # Adiciona mais 3 livros com autores, avaliações e acessos — número de queries deve permanecer idêntico (O(1))
        for idx in range(3):
            extra = Livro.objects.create(
                titulo=f'Obra Extra {idx}',
                categoria=self.cat_lit,
                editora=self.editora_escola,
                ano_publicacao=2020 + idx,
                arquivo_pdf=_criar_pdf_valido(f'extra-{idx}.pdf'),
                quantidade_total=2,
                quantidade_disponivel=2,
                dominio_publico=True,
                ativo=True,
                cadastrado_por=self.bib_perfil,
            )
            extra.autores.add(self.autor_machado)
            Avaliacao.objects.create(usuario=self.aluno_perfil, livro=extra, nota=5)
            RegistroAcesso.objects.create(
                usuario=self.aluno_perfil,
                livro=extra,
                tipo=RegistroAcesso.TIPO_DOWNLOAD,
            )

        with CaptureQueriesContext(connection) as ctx_apos:
            resp_apos = self.client.get(reverse('catalogo-livros-list'))
        self.assertEqual(resp_apos.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp_apos.data['results']), 7)
        self.assertEqual(len(ctx_inicial), len(ctx_apos))
        self.assertLessEqual(len(ctx_apos), 7)


class AvaliacoesLivroAPITests(CatalogoBaseMixin, APITestCase):
    """Testes de GET/POST /api/livros/<uuid>/avaliacoes/."""

    def test_criar_atualizar_e_listar_avaliacoes_paginadas(self):
        self.autenticar_como('2026-01001', self.aluno_password)
        url = reverse('catalogo-livros-avaliacoes', args=[self.livro_dp_pdf.id])

        # Criar primeira avaliação → 201
        r_create = self.client.post(url, {'nota': 4, 'comentario': 'Leitura ótima!'}, format='json')
        self.assertEqual(r_create.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r_create.data['nota'], 4)
        self.assertEqual(r_create.data['usuario_nome'], 'Maria Eduarda')
        self.assertEqual(r_create.data['usuario_turma'], '3º Ano A')

        # Reenviar POST pelo mesmo usuário → atualiza (200) mantendo 1 avaliação por usuário/livro
        r_update = self.client.post(url, {'nota': 5, 'comentario': 'Reavaliando: obra-prima!'}, format='json')
        self.assertEqual(r_update.status_code, status.HTTP_200_OK)
        self.assertEqual(r_update.data['nota'], 5)
        self.assertEqual(Avaliacao.objects.filter(livro=self.livro_dp_pdf).count(), 1)

        # Nota fora do intervalo 1..5 → 400
        r_invalida = self.client.post(url, {'nota': 6}, format='json')
        self.assertEqual(r_invalida.status_code, status.HTTP_400_BAD_REQUEST)

        # Listagem paginada
        r_list = self.client.get(url)
        self.assertEqual(r_list.status_code, status.HTTP_200_OK)
        self.assertEqual(r_list.data['count'], 1)
        self.assertEqual(r_list.data['results'][0]['comentario'], 'Reavaliando: obra-prima!')


class AuxiliaresCatalogoAPITests(CatalogoBaseMixin, APITestCase):
    """Testes de GET/POST /api/categorias/, /api/autores/ e /api/editoras/."""

    def test_aluno_lista_auxiliares_mas_recebe_403_no_post(self):
        self.autenticar_como('2026-01001', self.aluno_password)

        for nome_rota in ('catalogo-categorias-list', 'catalogo-autores-list', 'catalogo-editoras-list'):
            r_get = self.client.get(reverse(nome_rota))
            self.assertEqual(r_get.status_code, status.HTTP_200_OK)
            self.assertIn('results', r_get.data)

            r_post = self.client.post(reverse(nome_rota), {'nome': 'Novo Item'}, format='json')
            self.assertEqual(r_post.status_code, status.HTTP_403_FORBIDDEN)

    def test_bibliotecario_cria_auxiliares_e_bloqueia_duplicados(self):
        self.autenticar_como('BIB-2026-10', self.bib_password)

        # Categoria
        r_cat = self.client.post(
            reverse('catalogo-categorias-list'),
            {'nome': 'História do Brasil', 'descricao': 'Acervo histórico.'},
            format='json',
        )
        self.assertEqual(r_cat.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r_cat.data['slug'], 'historia-do-brasil')

        r_cat_dup = self.client.post(
            reverse('catalogo-categorias-list'),
            {'nome': 'história do brasil'},
            format='json',
        )
        self.assertEqual(r_cat_dup.status_code, status.HTTP_400_BAD_REQUEST)

        # Autor
        r_autor = self.client.post(
            reverse('catalogo-autores-list'),
            {'nome': 'Carolina Maria de Jesus', 'nacionalidade': 'Brasileira'},
            format='json',
        )
        self.assertEqual(r_autor.status_code, status.HTTP_201_CREATED)

        # Editora
        r_ed = self.client.post(
            reverse('catalogo-editoras-list'),
            {'nome': 'Editora Nova Fronteira', 'cidade': 'Rio de Janeiro'},
            format='json',
        )
        self.assertEqual(r_ed.status_code, status.HTTP_201_CREATED)

        # Confere contagem de total_livros contando apenas obras ativas
        r_cats = self.client.get(reverse('catalogo-categorias-list'), {'search': 'Matemática'})
        self.assertEqual(r_cats.status_code, status.HTTP_200_OK)
        self.assertEqual(r_cats.data['results'][0]['total_livros'], 1)


class GestaoAcervoEResumoAPITests(CatalogoBaseMixin, APITestCase):
    """Testes da T3.2 — Gestão do acervo (multipart PDF/EPUB), ativar/ocultar e /api/gestao/resumo/."""

    def test_aluno_recebe_403_na_gestao_de_livros_e_resumo(self):
        self.autenticar_como('2026-01001', self.aluno_password)

        self.assertEqual(
            self.client.get(reverse('gestao-livros-list')).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            self.client.post(reverse('gestao-livros-list'), {'titulo': 'Teste'}, format='json').status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            self.client.get(reverse('gestao-resumo')).status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_bibliotecario_lista_todas_as_obras_inclusive_ocultas_e_filtra_ativo(self):
        self.autenticar_como('BIB-2026-10', self.bib_password)

        resp_todas = self.client.get(reverse('gestao-livros-list'))
        self.assertEqual(resp_todas.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_todas.data['count'], 5)

        resp_ocultas = self.client.get(reverse('gestao-livros-list'), {'ativo': 'false'})
        self.assertEqual(resp_ocultas.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_ocultas.data['count'], 1)
        self.assertEqual(resp_ocultas.data['results'][0]['titulo'], 'Rascunho Interno')

    def test_upload_multipart_pdf_valido_preenche_cadastrado_por_e_protege_url(self):
        self.autenticar_como('BIB-2026-10', self.bib_password)

        resp = self.client.post(
            reverse('gestao-livros-list'),
            {
                'titulo': 'O Cortiço',
                'categoria': str(self.cat_lit.id),
                'editora': str(self.editora_escola.id),
                'autores_nomes': ['Aluísio Azevedo'],
                'ano_publicacao': 1890,
                'sinopse': 'Romance naturalista brasileiro.',
                'arquivo_pdf': _criar_pdf_valido('o-cortico.pdf'),
                'quantidade_total': 4,
                'dominio_publico': 'false',
                'ativo': 'true',
            },
            format='multipart',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertNotIn('arquivo_pdf', resp.data)
        self.assertEqual(resp.data['formato'], Livro.FORMATO_PDF)
        self.assertTrue(resp.data['possui_arquivo'])
        self.assertEqual(resp.data['cadastrado_por_nome'], 'Prof. Carlos Mendes')
        self.assertEqual(resp.data['quantidade_total'], 4)
        self.assertEqual(resp.data['quantidade_disponivel'], 4)
        self.assertEqual(resp.data['autores'][0]['nome'], 'Aluísio Azevedo')

    def test_upload_txt_renomeado_para_pdf_eh_rejeitado_com_400(self):
        self.autenticar_como('BIB-2026-10', self.bib_password)

        falso_pdf = SimpleUploadedFile('falso.pdf', b'nao e um pdf valido', content_type='application/pdf')
        resp = self.client.post(
            reverse('gestao-livros-list'),
            {
                'titulo': 'Arquivo Malicioso',
                'categoria': str(self.cat_lit.id),
                'ano_publicacao': 2025,
                'arquivo_pdf': falso_pdf,
                'dominio_publico': 'false',
            },
            format='multipart',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('arquivo_pdf', resp.data)

    def test_upload_epub_aceito_em_dominio_publico_e_rejeitado_em_aluguel(self):
        self.autenticar_como('BIB-2026-10', self.bib_password)

        # Em aluguel temporário (dominio_publico=False) → 400
        resp_negado = self.client.post(
            reverse('gestao-livros-list'),
            {
                'titulo': 'Aluguel EPUB Bloqueado',
                'categoria': str(self.cat_lit.id),
                'ano_publicacao': 2024,
                'arquivo_pdf': _criar_epub_valido('aluguel.epub'),
                'dominio_publico': 'false',
            },
            format='multipart',
        )
        self.assertEqual(resp_negado.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('arquivo_pdf', resp_negado.data)

        # Em domínio público (dominio_publico=True) → 201
        resp_ok = self.client.post(
            reverse('gestao-livros-list'),
            {
                'titulo': 'Iracema',
                'categoria': str(self.cat_lit.id),
                'ano_publicacao': 1865,
                'arquivo_pdf': _criar_epub_valido('iracema.epub'),
                'dominio_publico': 'true',
            },
            format='multipart',
        )
        self.assertEqual(resp_ok.status_code, status.HTTP_201_CREATED, resp_ok.data)
        self.assertEqual(resp_ok.data['formato'], Livro.FORMATO_EPUB)

    def test_patch_ocultar_ativar_obra_e_ajustar_estoque(self):
        self.autenticar_como('BIB-2026-10', self.bib_password)
        url = reverse('gestao-livros-detail', args=[self.livro_aluguel.id])

        # Ocultar obra via PATCH JSON
        r_ocultar = self.client.patch(url, {'ativo': False}, format='json')
        self.assertEqual(r_ocultar.status_code, status.HTTP_200_OK)
        self.assertFalse(r_ocultar.data['ativo'])

        # Aumentar quantidade_total de 3 -> 5 (disponível deve subir proporcionalmente de 2 -> 4)
        r_estoque = self.client.patch(url, {'ativo': True, 'quantidade_total': 5}, format='json')
        self.assertEqual(r_estoque.status_code, status.HTTP_200_OK)
        self.assertTrue(r_estoque.data['ativo'])
        self.assertEqual(r_estoque.data['quantidade_total'], 5)
        self.assertEqual(r_estoque.data['quantidade_disponivel'], 4)

    def test_resumo_agregado_retorna_metricas_em_uma_consulta_sql(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        Emprestimo.objects.create(
            usuario=self.aluno_perfil,
            livro=self.livro_aluguel,
            data_prevista_devolucao=timezone.localdate() + timedelta(days=7),
            status=Emprestimo.STATUS_ATIVO,
        )
        Emprestimo.objects.create(
            usuario=self.outro_aluno_perfil,
            livro=self.livro_esgotado,
            data_prevista_devolucao=timezone.localdate() - timedelta(days=2),
            status=Emprestimo.STATUS_ATRASADO,
        )
        RegistroAcesso.objects.create(
            usuario=self.aluno_perfil,
            livro=self.livro_aluguel,
            tipo=RegistroAcesso.TIPO_LEITURA,
        )
        RegistroAcesso.objects.create(
            usuario=self.aluno_perfil,
            livro=self.livro_dp_pdf,
            tipo=RegistroAcesso.TIPO_DOWNLOAD,
        )

        self.autenticar_como('BIB-2026-10', self.bib_password)
        with CaptureQueriesContext(connection) as ctx:
            resp = self.client.get(reverse('gestao-resumo'))

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['total_obras'], 5)
        self.assertEqual(resp.data['obras_ativas'], 4)
        self.assertEqual(resp.data['emprestimos_ativos'], 1)
        self.assertEqual(resp.data['em_atraso'], 1)
        self.assertEqual(resp.data['total_leituras'], 1)
        self.assertEqual(resp.data['total_downloads'], 1)
        self.assertEqual(resp.data['total_alunos'], 2)
        # 2 queries de auth (user + perfil) + 1 única query SQL agregada para todas as métricas
        self.assertLessEqual(len(ctx), 3)
