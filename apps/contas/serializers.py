from django.contrib.auth import get_user_model
from django.contrib.auth.models import update_last_login
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from .models import PerfilUsuario, Turma
from .permissions import obter_perfil_usuario
from .services import atualizar_aluno, criar_aluno
from .validators import validar_matricula

User = get_user_model()


def _converter_django_validation_error(exc):
    if hasattr(exc, 'message_dict'):
        return serializers.ValidationError(exc.message_dict)
    return serializers.ValidationError({'detail': list(exc.messages)})


class TurmaResumoSerializer(serializers.ModelSerializer):
    turno_display = serializers.CharField(source='get_turno_display', read_only=True)

    class Meta:
        model = Turma
        fields = ['id', 'nome', 'turno', 'turno_display', 'ano_letivo', 'ativa']


class TurmaSerializer(serializers.ModelSerializer):
    turno_display = serializers.CharField(source='get_turno_display', read_only=True)
    total_alunos = serializers.SerializerMethodField()

    class Meta:
        model = Turma
        fields = [
            'id',
            'nome',
            'turno',
            'turno_display',
            'ano_letivo',
            'ativa',
            'total_alunos',
            'criado_em',
            'atualizado_em',
        ]
        read_only_fields = ['id', 'turno_display', 'total_alunos', 'criado_em', 'atualizado_em']

    @extend_schema_field(serializers.IntegerField)
    def get_total_alunos(self, obj):
        if hasattr(obj, 'total_alunos'):
            return obj.total_alunos
        return obj.alunos.filter(tipo=PerfilUsuario.TIPO_ALUNO).count()

    def validate_nome(self, value):
        nome = value.strip()
        if not nome:
            raise serializers.ValidationError(_('O nome da turma é obrigatório.'))
        return nome

    def validate(self, attrs):
        nome = attrs.get('nome', getattr(self.instance, 'nome', None))
        ano_letivo = attrs.get('ano_letivo', getattr(self.instance, 'ano_letivo', None))
        if nome and ano_letivo is not None:
            qs = Turma.objects.filter(nome__iexact=nome, ano_letivo=ano_letivo)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError({
                    'nome': _('Já existe uma turma com este nome para o ano letivo informado.'),
                })
        return attrs


class PerfilUsuarioSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source='user.id', read_only=True, allow_null=True)
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)
    eh_bibliotecario = serializers.BooleanField(read_only=True)
    turma = TurmaResumoSerializer(read_only=True)

    class Meta:
        model = PerfilUsuario
        fields = [
            'id',
            'user_id',
            'nome',
            'email',
            'matricula',
            'tipo',
            'tipo_display',
            'eh_bibliotecario',
            'turma',
            'telefone',
            'ativo',
            'precisa_trocar_senha',
            'criado_em',
            'atualizado_em',
        ]


def serializar_usuario_autenticado(user, perfil=None):
    """Monta o payload padrão do usuário autenticado (usado em /login/ e /me/)."""
    if perfil is not None:
        return PerfilUsuarioSerializer(perfil).data

    return {
        'id': None,
        'user_id': user.id,
        'nome': user.get_full_name().strip() or user.username,
        'email': user.email,
        'matricula': None,
        'tipo': PerfilUsuario.TIPO_BIBLIOTECARIO,
        'tipo_display': dict(PerfilUsuario.TIPO_CHOICES)[PerfilUsuario.TIPO_BIBLIOTECARIO],
        'eh_bibliotecario': bool(user.is_staff or user.is_superuser),
        'turma': None,
        'telefone': None,
        'ativo': user.is_active,
        'precisa_trocar_senha': False,
        'criado_em': user.date_joined,
        'atualizado_em': user.date_joined,
    }


class LoginSerializer(serializers.Serializer):
    identificador = serializers.CharField(
        help_text=_('E-mail institucional ou número de matrícula.'),
    )
    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        style={'input_type': 'password'},
    )

    def validate(self, attrs):
        identificador = (attrs.get('identificador') or '').strip()
        password = attrs.get('password') or ''

        if not identificador or not password:
            raise AuthenticationFailed(
                _('Credenciais inválidas. Informe seu e-mail ou matrícula e sua senha.')
            )

        perfil = (
            PerfilUsuario.objects.select_related('user', 'turma')
            .filter(Q(email__iexact=identificador) | Q(matricula__iexact=identificador))
            .first()
        )

        user = None
        if perfil is not None:
            user = perfil.user
            if user is None or not user.check_password(password):
                raise AuthenticationFailed(
                    _('Credenciais inválidas. Verifique seu e-mail/matrícula e senha.')
                )
            if not user.is_active or not perfil.ativo:
                raise PermissionDenied(
                    _('Esta conta está desativada. Entre em contato com a biblioteca.')
                )
        else:
            # Fallback para superusuário/staff sem PerfilUsuario vinculado
            user = User.objects.filter(
                Q(email__iexact=identificador) | Q(username__iexact=identificador)
            ).first()
            if user is None or not user.check_password(password):
                raise AuthenticationFailed(
                    _('Credenciais inválidas. Verifique seu e-mail/matrícula e senha.')
                )
            if not user.is_active:
                raise PermissionDenied(
                    _('Esta conta está desativada. Entre em contato com a biblioteca.')
                )
            perfil = obter_perfil_usuario(user)
            if perfil is not None and not perfil.ativo:
                raise PermissionDenied(
                    _('Esta conta está desativada. Entre em contato com a biblioteca.')
                )
            if perfil is None and not (user.is_staff or user.is_superuser):
                raise AuthenticationFailed(
                    _('Credenciais inválidas. Verifique seu e-mail/matrícula e senha.')
                )

        refresh = RefreshToken.for_user(user)
        update_last_login(None, user)

        return {
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'usuario': serializar_usuario_autenticado(user, perfil),
        }


class LoginResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    usuario = PerfilUsuarioSerializer()


class AranduTokenRefreshSerializer(TokenRefreshSerializer):
    """Renova o access token garantindo que o usuário e o perfil continuam ativos."""

    def validate(self, attrs):
        try:
            refresh = RefreshToken(attrs['refresh'])
        except TokenError:
            raise AuthenticationFailed(_('Token de atualização inválido ou expirado.'))

        user_id = refresh.payload.get('user_id')
        user = User.objects.filter(pk=user_id).first() if user_id is not None else None
        if user is None:
            raise AuthenticationFailed(_('Usuário associado ao token não encontrado.'))

        perfil = obter_perfil_usuario(user)
        if not user.is_active or (perfil is not None and not perfil.ativo):
            raise PermissionDenied(
                _('Esta conta está desativada. Não é possível renovar a sessão.')
            )

        return super().validate(attrs)


class ResumoEmprestimosSerializer(serializers.Serializer):
    ativos = serializers.IntegerField()
    atrasados = serializers.IntegerField()
    devolvidos = serializers.IntegerField()
    total = serializers.IntegerField()


class MeResponseSerializer(PerfilUsuarioSerializer):
    username = serializers.CharField()
    resumo_emprestimos = ResumoEmprestimosSerializer()

    class Meta(PerfilUsuarioSerializer.Meta):
        fields = PerfilUsuarioSerializer.Meta.fields + ['username', 'resumo_emprestimos']


class EsqueciSenhaSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return value.strip().lower()


class MensagemDetalheSerializer(serializers.Serializer):
    detail = serializers.CharField()


class RedefinirSenhaSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    nova_senha = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        style={'input_type': 'password'},
    )
    confirmar_nova_senha = serializers.CharField(
        write_only=True,
        required=False,
        trim_whitespace=False,
        style={'input_type': 'password'},
    )

    def validate(self, attrs):
        nova_senha = attrs.get('nova_senha', '')
        confirmar = attrs.get('confirmar_nova_senha')
        if confirmar is not None and nova_senha != confirmar:
            raise serializers.ValidationError({
                'confirmar_nova_senha': _('As senhas informadas não coincidem.'),
            })

        try:
            user_id = force_str(urlsafe_base64_decode(attrs['uid']))
            user = User.objects.get(pk=user_id)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise serializers.ValidationError({
                'token': _('Token inválido ou expirado. Solicite uma nova recuperação de senha.'),
            })

        perfil = obter_perfil_usuario(user)
        if not user.is_active or (perfil is not None and not perfil.ativo):
            raise serializers.ValidationError({
                'token': _('Token inválido ou expirado. Solicite uma nova recuperação de senha.'),
            })

        if not default_token_generator.check_token(user, attrs['token']):
            raise serializers.ValidationError({
                'token': _('Token inválido ou expirado. Solicite uma nova recuperação de senha.'),
            })

        try:
            validate_password(nova_senha, user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({'nova_senha': list(exc.messages)})

        attrs['user'] = user
        attrs['perfil'] = perfil
        return attrs


class AlunoGestaoSerializer(serializers.ModelSerializer):
    """Leitura de alunos na gestão do bibliotecário."""

    user_id = serializers.IntegerField(source='user.id', read_only=True, allow_null=True)
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)
    turma_detalhes = TurmaResumoSerializer(source='turma', read_only=True)

    class Meta:
        model = PerfilUsuario
        fields = [
            'id',
            'user_id',
            'nome',
            'email',
            'matricula',
            'tipo',
            'tipo_display',
            'turma',
            'turma_detalhes',
            'telefone',
            'ativo',
            'precisa_trocar_senha',
            'criado_em',
            'atualizado_em',
        ]
        read_only_fields = fields


class AlunoCreateSerializer(serializers.Serializer):
    """Entrada para cadastro transacional de novo aluno pelo bibliotecário."""

    nome = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    matricula = serializers.CharField(max_length=30, validators=[validar_matricula])
    turma = serializers.PrimaryKeyRelatedField(
        queryset=Turma.objects.all(),
        required=False,
        allow_null=True,
    )
    telefone = serializers.CharField(max_length=20, required=False, allow_blank=True, allow_null=True)
    ativo = serializers.BooleanField(required=False, default=True)
    senha = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        allow_null=True,
        trim_whitespace=False,
        style={'input_type': 'password'},
        help_text=_('Opcional. Se omitida, uma senha temporária segura será gerada automaticamente.'),
    )
    precisa_trocar_senha = serializers.BooleanField(required=False, default=True)

    def create(self, validated_data):
        senha = validated_data.pop('senha', None) or None
        try:
            perfil, senha_temporaria = criar_aluno(senha=senha, **validated_data)
        except DjangoValidationError as exc:
            raise _converter_django_validation_error(exc)
        self.senha_temporaria_gerada = senha_temporaria
        return perfil


class AlunoCreateResponseSerializer(AlunoGestaoSerializer):
    senha_temporaria = serializers.CharField(
        read_only=True,
        allow_null=True,
        help_text=_('Retornada uma única vez quando a senha inicial não é informada no cadastro.'),
    )

    class Meta(AlunoGestaoSerializer.Meta):
        fields = AlunoGestaoSerializer.Meta.fields + ['senha_temporaria']


class AlunoUpdateSerializer(serializers.Serializer):
    """Entrada para edição/desativação transacional de aluno pelo bibliotecário."""

    nome = serializers.CharField(max_length=150, required=False)
    email = serializers.EmailField(required=False)
    matricula = serializers.CharField(max_length=30, required=False, validators=[validar_matricula])
    turma = serializers.PrimaryKeyRelatedField(
        queryset=Turma.objects.all(),
        required=False,
        allow_null=True,
    )
    telefone = serializers.CharField(max_length=20, required=False, allow_blank=True, allow_null=True)
    ativo = serializers.BooleanField(required=False)
    precisa_trocar_senha = serializers.BooleanField(required=False)
    senha = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=False,
        trim_whitespace=False,
        style={'input_type': 'password'},
    )

    def update(self, instance, validated_data):
        try:
            return atualizar_aluno(instance, **validated_data)
        except DjangoValidationError as exc:
            raise _converter_django_validation_error(exc)
