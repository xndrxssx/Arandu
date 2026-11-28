from django.db import connection
from django.db.models import Avg, Count, FloatField, IntegerField, OuterRef, Prefetch, Q, Subquery, Value
from django.db.models.functions import Coalesce
from django.utils.translation import gettext_lazy as _
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.contas.models import PerfilUsuario
from apps.contas.permissions import IsBibliotecario, IsUsuarioAtivo, obter_perfil_usuario

from .filters import LivroFilter, LivroGestaoFilter
from .models import Autor, Avaliacao, Categoria, Editora, Emprestimo, Livro, RegistroAcesso
from .serializers import (
    AutorSerializer,
    AvaliacaoCreateUpdateSerializer,
    AvaliacaoSerializer,
    CategoriaSerializer,
    EditoraSerializer,
    GestaoResumoSerializer,
    LivroDetailSerializer,
    LivroGestaoSerializer,
    LivroGestaoWriteSerializer,
    LivroListSerializer,
)


def _construir_queryset_catalogo(request, incluir_minha_avaliacao=False):
    """Monta queryset otimizado de livros ativos sem N+1 nem multiplicação de linhas em agregações."""
    nota_media_subquery = Subquery(
        Avaliacao.objects.filter(livro=OuterRef('pk'))
        .order_by()
        .values('livro')
        .annotate(media=Avg('nota'))
        .values('media')[:1],
        output_field=FloatField(),
    )
    total_avaliacoes_subquery = Subquery(
        Avaliacao.objects.filter(livro=OuterRef('pk'))
        .order_by()
        .values('livro')
        .annotate(total=Count('id'))
        .values('total')[:1],
        output_field=IntegerField(),
    )
    total_acessos_subquery = Subquery(
        RegistroAcesso.objects.filter(livro=OuterRef('pk'))
        .order_by()
        .values('livro')
        .annotate(total=Count('id'))
        .values('total')[:1],
        output_field=IntegerField(),
    )

    prefetches = ['autores']
    perfil = obter_perfil_usuario(getattr(request, 'user', None))
    if perfil is not None:
        prefetches.append(
            Prefetch(
                'emprestimos',
                queryset=Emprestimo.objects.filter(
                    usuario=perfil,
                    status__in=[Emprestimo.STATUS_ATIVO, Emprestimo.STATUS_ATRASADO],
                ).order_by('-data_emprestimo'),
                to_attr='emprestimos_abertos_usuario',
            )
        )
        if incluir_minha_avaliacao:
            prefetches.append(
                Prefetch(
                    'avaliacoes',
                    queryset=Avaliacao.objects.select_related('usuario', 'usuario__turma').filter(
                        usuario=perfil
                    ),
                    to_attr='avaliacoes_usuario',
                )
            )

    return (
        Livro.objects.filter(ativo=True)
        .select_related('categoria', 'editora', 'cadastrado_por')
        .prefetch_related(*prefetches)
        .annotate(
            nota_media=nota_media_subquery,
            total_avaliacoes=Coalesce(total_avaliacoes_subquery, Value(0)),
            total_acessos=Coalesce(total_acessos_subquery, Value(0)),
        )
        .order_by('titulo')
    )


@extend_schema_view(
    list=extend_schema(
        tags=['Catálogo'],
        summary='Listar obras ativas do catálogo',
        responses={200: LivroListSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=['Catálogo'],
        summary='Detalhar obra do catálogo',
        responses={200: LivroDetailSerializer},
    ),
)
class LivroCatalogoViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Catálogo paginado, filtros, detalhes e avaliações de obras ativas."""

    permission_classes = [IsAuthenticated, IsUsuarioAtivo]
    http_method_names = ['get', 'post', 'head', 'options']
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = LivroFilter
    search_fields = ['titulo', 'autores__nome', 'isbn']
    ordering_fields = ['titulo', 'ano_publicacao', 'criado_em', 'nota_media', 'total_acessos']
    ordering = ['titulo']

    def get_queryset(self):
        incluir_avaliacao = self.action == 'retrieve'
        return _construir_queryset_catalogo(
            self.request,
            incluir_minha_avaliacao=incluir_avaliacao,
        )

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return LivroDetailSerializer
        if self.action == 'avaliacoes':
            if self.request.method == 'POST':
                return AvaliacaoCreateUpdateSerializer
            return AvaliacaoSerializer
        return LivroListSerializer

    def filter_queryset(self, queryset):
        return super().filter_queryset(queryset).distinct()

    @extend_schema(
        methods=['GET'],
        tags=['Catálogo'],
        summary='Listar avaliações da obra (paginado)',
        responses={200: AvaliacaoSerializer(many=True)},
    )
    @extend_schema(
        methods=['POST'],
        tags=['Catálogo'],
        summary='Criar ou atualizar avaliação da obra (1 por usuário/livro)',
        request=AvaliacaoCreateUpdateSerializer,
        responses={200: AvaliacaoSerializer, 201: AvaliacaoSerializer},
    )
    @action(detail=True, methods=['get', 'post'], url_path='avaliacoes', url_name='avaliacoes')
    def avaliacoes(self, request, pk=None):
        livro = self.get_object()

        if request.method == 'GET':
            qs = (
                Avaliacao.objects.filter(livro=livro)
                .select_related('usuario', 'usuario__turma')
                .order_by('-criado_em')
            )
            page = self.paginate_queryset(qs)
            if page is not None:
                serializer = AvaliacaoSerializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            serializer = AvaliacaoSerializer(qs, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        perfil = obter_perfil_usuario(request.user)
        if perfil is None:
            return Response(
                {
                    'detail': _(
                        'É necessário possuir um perfil escolar vinculado para avaliar obras.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = AvaliacaoCreateUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        avaliacao, criada = Avaliacao.objects.update_or_create(
            usuario=perfil,
            livro=livro,
            defaults={
                'nota': serializer.validated_data['nota'],
                'comentario': serializer.validated_data.get('comentario'),
            },
        )
        avaliacao = (
            Avaliacao.objects.select_related('usuario', 'usuario__turma')
            .get(pk=avaliacao.pk)
        )
        dados = AvaliacaoSerializer(avaliacao).data
        return Response(
            dados,
            status=status.HTTP_201_CREATED if criada else status.HTTP_200_OK,
        )


class AuxiliarCatalogoPermissaoMixin:
    """GET liberado a qualquer usuário ativo; POST restrito a bibliotecários."""

    def get_permissions(self):
        if self.action == 'create':
            return [IsAuthenticated(), IsBibliotecario()]
        return [IsAuthenticated(), IsUsuarioAtivo()]


@extend_schema_view(
    list=extend_schema(tags=['Auxiliares do Catálogo'], summary='Listar categorias do acervo'),
    retrieve=extend_schema(tags=['Auxiliares do Catálogo'], summary='Detalhar categoria'),
    create=extend_schema(tags=['Auxiliares do Catálogo'], summary='Cadastrar nova categoria (Bibliotecário)'),
)
class CategoriaViewSet(
    AuxiliarCatalogoPermissaoMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = CategoriaSerializer
    http_method_names = ['get', 'post', 'head', 'options']
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nome', 'slug', 'descricao']
    ordering_fields = ['nome', 'criado_em', 'total_livros']
    ordering = ['nome']

    def get_queryset(self):
        return Categoria.objects.annotate(
            total_livros=Count('livros', filter=Q(livros__ativo=True), distinct=True)
        ).order_by('nome')


@extend_schema_view(
    list=extend_schema(tags=['Auxiliares do Catálogo'], summary='Listar autores cadastrados'),
    retrieve=extend_schema(tags=['Auxiliares do Catálogo'], summary='Detalhar autor'),
    create=extend_schema(tags=['Auxiliares do Catálogo'], summary='Cadastrar novo autor (Bibliotecário)'),
)
class AutorViewSet(
    AuxiliarCatalogoPermissaoMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = AutorSerializer
    http_method_names = ['get', 'post', 'head', 'options']
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nome', 'nacionalidade']
    ordering_fields = ['nome', 'criado_em', 'total_livros']
    ordering = ['nome']

    def get_queryset(self):
        return Autor.objects.annotate(
            total_livros=Count('livros', filter=Q(livros__ativo=True), distinct=True)
        ).order_by('nome')


@extend_schema_view(
    list=extend_schema(tags=['Auxiliares do Catálogo'], summary='Listar editoras cadastradas'),
    retrieve=extend_schema(tags=['Auxiliares do Catálogo'], summary='Detalhar editora'),
    create=extend_schema(tags=['Auxiliares do Catálogo'], summary='Cadastrar nova editora (Bibliotecário)'),
)
class EditoraViewSet(
    AuxiliarCatalogoPermissaoMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = EditoraSerializer
    http_method_names = ['get', 'post', 'head', 'options']
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nome', 'cidade']
    ordering_fields = ['nome', 'criado_em', 'total_livros']
    ordering = ['nome']

    def get_queryset(self):
        return Editora.objects.annotate(
            total_livros=Count('livros', filter=Q(livros__ativo=True), distinct=True)
        ).order_by('nome')


def _construir_queryset_gestao_livros():
    """Queryset completo de gestão (inclui obras ativas e ocultas) com agregações sem N+1."""
    nota_media_subquery = Subquery(
        Avaliacao.objects.filter(livro=OuterRef('pk'))
        .order_by()
        .values('livro')
        .annotate(media=Avg('nota'))
        .values('media')[:1],
        output_field=FloatField(),
    )
    total_avaliacoes_subquery = Subquery(
        Avaliacao.objects.filter(livro=OuterRef('pk'))
        .order_by()
        .values('livro')
        .annotate(total=Count('id'))
        .values('total')[:1],
        output_field=IntegerField(),
    )
    total_acessos_subquery = Subquery(
        RegistroAcesso.objects.filter(livro=OuterRef('pk'))
        .order_by()
        .values('livro')
        .annotate(total=Count('id'))
        .values('total')[:1],
        output_field=IntegerField(),
    )
    emprestimos_ativos_subquery = Subquery(
        Emprestimo.objects.filter(
            livro=OuterRef('pk'),
            status__in=[Emprestimo.STATUS_ATIVO, Emprestimo.STATUS_ATRASADO],
        )
        .order_by()
        .values('livro')
        .annotate(total=Count('id'))
        .values('total')[:1],
        output_field=IntegerField(),
    )

    return (
        Livro.objects.all()
        .select_related('categoria', 'editora', 'cadastrado_por')
        .prefetch_related('autores')
        .annotate(
            nota_media=nota_media_subquery,
            total_avaliacoes=Coalesce(total_avaliacoes_subquery, Value(0)),
            total_acessos=Coalesce(total_acessos_subquery, Value(0)),
            emprestimos_ativos=Coalesce(emprestimos_ativos_subquery, Value(0)),
        )
        .order_by('-criado_em')
    )


@extend_schema_view(
    list=extend_schema(
        tags=['Gestão — Acervo'],
        summary='Listar todas as obras do acervo (ativas e ocultas)',
        responses={200: LivroGestaoSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=['Gestão — Acervo'],
        summary='Detalhar obra na gestão do acervo',
        responses={200: LivroGestaoSerializer},
    ),
    create=extend_schema(
        tags=['Gestão — Acervo'],
        summary='Cadastrar obra com upload de PDF/EPUB e capa',
        request=LivroGestaoWriteSerializer,
        responses={201: LivroGestaoSerializer},
    ),
    partial_update=extend_schema(
        tags=['Gestão — Acervo'],
        summary='Atualizar obra, substituir arquivo ou ativar/ocultar no catálogo',
        request=LivroGestaoWriteSerializer,
        responses={200: LivroGestaoSerializer},
    ),
)
class LivroGestaoViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """CRUD de gestão do acervo exclusivo para bibliotecários (suporta multipart/form-data e JSON)."""

    permission_classes = [IsAuthenticated, IsBibliotecario]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    http_method_names = ['get', 'post', 'patch', 'head', 'options']
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = LivroGestaoFilter
    search_fields = ['titulo', 'autores__nome', 'isbn']
    ordering_fields = [
        'titulo',
        'ano_publicacao',
        'criado_em',
        'atualizado_em',
        'ativo',
        'quantidade_disponivel',
        'total_acessos',
    ]
    ordering = ['-criado_em']

    def get_queryset(self):
        return _construir_queryset_gestao_livros()

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return LivroGestaoWriteSerializer
        return LivroGestaoSerializer

    def filter_queryset(self, queryset):
        return super().filter_queryset(queryset).distinct()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        livro = serializer.save()

        livro_anotado = self.get_queryset().get(pk=livro.pk)
        dados = LivroGestaoSerializer(livro_anotado, context=self.get_serializer_context()).data
        headers = self.get_success_headers(dados)
        return Response(dados, status=status.HTTP_201_CREATED, headers=headers)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        livro = serializer.save()

        livro_anotado = self.get_queryset().get(pk=livro.pk)
        dados = LivroGestaoSerializer(livro_anotado, context=self.get_serializer_context()).data
        return Response(dados, status=status.HTTP_200_OK)


class GestaoResumoView(APIView):
    """Retorna métricas agregadas do painel de gestão em uma única consulta SQL."""

    permission_classes = [IsAuthenticated, IsBibliotecario]

    @extend_schema(
        tags=['Gestão — Acervo'],
        summary='Resumo agregado de indicadores da biblioteca',
        responses={200: GestaoResumoSerializer},
    )
    def get(self, request):
        livro_table = connection.ops.quote_name(Livro._meta.db_table)
        emp_table = connection.ops.quote_name(Emprestimo._meta.db_table)
        reg_table = connection.ops.quote_name(RegistroAcesso._meta.db_table)
        perfil_table = connection.ops.quote_name(PerfilUsuario._meta.db_table)

        sql = f"""
            SELECT
                (SELECT COUNT(*) FROM {livro_table}) AS total_obras,
                (SELECT COUNT(*) FROM {livro_table} WHERE ativo = TRUE) AS obras_ativas,
                (SELECT COUNT(*) FROM {emp_table} WHERE status = %s) AS emprestimos_ativos,
                (SELECT COUNT(*) FROM {emp_table} WHERE status = %s) AS em_atraso,
                (SELECT COUNT(*) FROM {reg_table} WHERE tipo = %s) AS total_leituras,
                (SELECT COUNT(*) FROM {reg_table} WHERE tipo = %s) AS total_downloads,
                (SELECT COUNT(*) FROM {perfil_table} WHERE tipo = %s) AS total_alunos
        """
        params = [
            Emprestimo.STATUS_ATIVO,
            Emprestimo.STATUS_ATRASADO,
            RegistroAcesso.TIPO_LEITURA,
            RegistroAcesso.TIPO_DOWNLOAD,
            PerfilUsuario.TIPO_ALUNO,
        ]

        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            row = cursor.fetchone()

        payload = {
            'total_obras': int(row[0] or 0),
            'obras_ativas': int(row[1] or 0),
            'emprestimos_ativos': int(row[2] or 0),
            'em_atraso': int(row[3] or 0),
            'total_leituras': int(row[4] or 0),
            'total_downloads': int(row[5] or 0),
            'total_alunos': int(row[6] or 0),
        }
        return Response(payload, status=status.HTTP_200_OK)
