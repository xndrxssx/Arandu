from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.db import transaction
from django.db.models import Count, Q
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.translation import gettext_lazy as _
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import filters, mixins, status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenRefreshView

from apps.arandu.models import Emprestimo

from .emails import enviar_email_reset_senha
from .models import PerfilUsuario, Turma
from .permissions import IsBibliotecario, IsUsuarioAtivo, obter_perfil_usuario
from .serializers import (
    AlunoCreateResponseSerializer,
    AlunoCreateSerializer,
    AlunoGestaoSerializer,
    AlunoUpdateSerializer,
    AranduTokenRefreshSerializer,
    EsqueciSenhaSerializer,
    LoginResponseSerializer,
    LoginSerializer,
    MensagemDetalheSerializer,
    MeResponseSerializer,
    RedefinirSenhaSerializer,
    TurmaSerializer,
    serializar_usuario_autenticado,
)

User = get_user_model()


class LoginView(APIView):
    """Autenticação JWT por e-mail institucional ou matrícula + senha."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = 'login'

    def get_authenticate_header(self, request):
        return 'Bearer realm="api"'

    @extend_schema(
        tags=['Autenticação'],
        summary='Login com e-mail ou matrícula',
        request=LoginSerializer,
        responses={200: LoginResponseSerializer},
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


@extend_schema(
    tags=['Autenticação'],
    summary='Renovar token de acesso JWT',
)
class CustomTokenRefreshView(TokenRefreshView):
    """Renova o token JWT verificando se a conta permanece ativa."""

    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = AranduTokenRefreshSerializer

    def get_authenticate_header(self, request):
        return 'Bearer realm="api"'


class MeView(APIView):
    """Retorna os dados do usuário autenticado, perfil, turma e resumo de empréstimos."""

    permission_classes = [IsAuthenticated, IsUsuarioAtivo]

    @extend_schema(
        tags=['Autenticação'],
        summary='Perfil do usuário autenticado e resumo de empréstimos',
        responses={200: MeResponseSerializer},
    )
    def get(self, request):
        user = request.user
        perfil = (
            PerfilUsuario.objects.select_related('turma', 'user')
            .filter(user=user)
            .first()
        )
        dados = serializar_usuario_autenticado(user, perfil)
        dados['username'] = user.username

        if perfil is not None:
            resumo = Emprestimo.objects.filter(usuario=perfil).aggregate(
                ativos=Count('id', filter=Q(status=Emprestimo.STATUS_ATIVO)),
                atrasados=Count('id', filter=Q(status=Emprestimo.STATUS_ATRASADO)),
                devolvidos=Count('id', filter=Q(status=Emprestimo.STATUS_DEVOLVIDO)),
                total=Count('id'),
            )
        else:
            resumo = {'ativos': 0, 'atrasados': 0, 'devolvidos': 0, 'total': 0}

        dados['resumo_emprestimos'] = resumo
        return Response(dados, status=status.HTTP_200_OK)


class EsqueciSenhaView(APIView):
    """Solicita recuperação de senha enviando e-mail HTML com uid e token (resposta sempre 200)."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = 'password_reset'

    @extend_schema(
        tags=['Autenticação'],
        summary='Solicitar recuperação de senha por e-mail',
        request=EsqueciSenhaSerializer,
        responses={200: MensagemDetalheSerializer},
    )
    def post(self, request):
        serializer = EsqueciSenhaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']

        perfil = (
            PerfilUsuario.objects.select_related('user')
            .filter(email__iexact=email)
            .first()
        )
        user = perfil.user if perfil is not None else User.objects.filter(email__iexact=email).first()
        if perfil is None and user is not None:
            perfil = obter_perfil_usuario(user)

        conta_ativa = bool(
            user is not None
            and user.is_active
            and (perfil is None or perfil.ativo)
        )
        if conta_ativa:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            enviar_email_reset_senha(user=user, uid=uid, token=token, perfil=perfil)

        return Response(
            {
                'detail': _(
                    'Se o e-mail estiver cadastrado e ativo, você receberá as instruções '
                    'para redefinir sua senha.'
                )
            },
            status=status.HTTP_200_OK,
        )


class RedefinirSenhaView(APIView):
    """Valida uid/token de uso único e aplica a nova senha seguindo AUTH_PASSWORD_VALIDATORS."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = 'password_reset'

    @extend_schema(
        tags=['Autenticação'],
        summary='Redefinir senha com uid e token',
        request=RedefinirSenhaSerializer,
        responses={200: MensagemDetalheSerializer},
    )
    def post(self, request):
        serializer = RedefinirSenhaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data['user']
        perfil = serializer.validated_data['perfil']
        nova_senha = serializer.validated_data['nova_senha']

        with transaction.atomic():
            user.set_password(nova_senha)
            user.save(update_fields=['password'])

            if perfil is not None and perfil.precisa_trocar_senha:
                perfil.precisa_trocar_senha = False
                perfil.save(update_fields=['precisa_trocar_senha', 'atualizado_em'])

        return Response(
            {'detail': _('Senha redefinida com sucesso.')},
            status=status.HTTP_200_OK,
        )


@extend_schema_view(
    list=extend_schema(tags=['Gestão — Alunos'], summary='Listar alunos cadastrados'),
    retrieve=extend_schema(tags=['Gestão — Alunos'], summary='Detalhar aluno'),
    create=extend_schema(
        tags=['Gestão — Alunos'],
        summary='Cadastrar aluno (transacional)',
        request=AlunoCreateSerializer,
        responses={201: AlunoCreateResponseSerializer},
    ),
    partial_update=extend_schema(
        tags=['Gestão — Alunos'],
        summary='Atualizar ou ativar/desativar aluno (transacional)',
        request=AlunoUpdateSerializer,
        responses={200: AlunoGestaoSerializer},
    ),
)
class AlunoGestaoViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """CRUD transacional de alunos exclusivo para bibliotecários."""

    permission_classes = [IsAuthenticated, IsBibliotecario]
    http_method_names = ['get', 'post', 'patch', 'head', 'options']
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['ativo', 'turma', 'turma__turno', 'turma__ano_letivo']
    search_fields = ['nome', 'matricula', 'email', 'turma__nome']
    ordering_fields = ['nome', 'matricula', 'criado_em', 'ativo']
    ordering = ['nome']

    def get_queryset(self):
        return (
            PerfilUsuario.objects.filter(tipo=PerfilUsuario.TIPO_ALUNO)
            .select_related('turma', 'user')
            .order_by('nome')
        )

    def get_serializer_class(self):
        if self.action == 'create':
            return AlunoCreateSerializer
        if self.action in ('update', 'partial_update'):
            return AlunoUpdateSerializer
        return AlunoGestaoSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        perfil = serializer.save()

        dados_resposta = AlunoGestaoSerializer(perfil, context=self.get_serializer_context()).data
        senha_temporaria = getattr(serializer, 'senha_temporaria_gerada', None)
        if senha_temporaria is not None:
            dados_resposta['senha_temporaria'] = senha_temporaria

        headers = self.get_success_headers(dados_resposta)
        return Response(dados_resposta, status=status.HTTP_201_CREATED, headers=headers)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        perfil_atualizado = serializer.save()

        dados_resposta = AlunoGestaoSerializer(
            perfil_atualizado,
            context=self.get_serializer_context(),
        ).data
        return Response(dados_resposta, status=status.HTTP_200_OK)


@extend_schema_view(
    list=extend_schema(tags=['Gestão — Turmas'], summary='Listar turmas escolares'),
    retrieve=extend_schema(tags=['Gestão — Turmas'], summary='Detalhar turma escolar'),
    create=extend_schema(tags=['Gestão — Turmas'], summary='Cadastrar turma escolar'),
    partial_update=extend_schema(tags=['Gestão — Turmas'], summary='Atualizar turma escolar'),
)
class TurmaGestaoViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """CRUD de turmas escolares exclusivo para bibliotecários."""

    permission_classes = [IsAuthenticated, IsBibliotecario]
    serializer_class = TurmaSerializer
    http_method_names = ['get', 'post', 'patch', 'head', 'options']
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['turno', 'ano_letivo', 'ativa']
    search_fields = ['nome']
    ordering_fields = ['ano_letivo', 'nome', 'turno', 'criado_em']
    ordering = ['-ano_letivo', 'nome']

    def get_queryset(self):
        return Turma.objects.annotate(
            total_alunos=Count('alunos', filter=Q(alunos__tipo=PerfilUsuario.TIPO_ALUNO))
        ).order_by('-ano_letivo', 'nome')
