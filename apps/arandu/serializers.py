import os

from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.contas.permissions import obter_perfil_usuario

from .models import Autor, Avaliacao, Categoria, Editora, Emprestimo, Livro


class CategoriaResumoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categoria
        fields = ['id', 'nome', 'slug']


class CategoriaSerializer(serializers.ModelSerializer):
    total_livros = serializers.SerializerMethodField()

    class Meta:
        model = Categoria
        fields = ['id', 'nome', 'slug', 'descricao', 'total_livros', 'criado_em']
        read_only_fields = ['id', 'slug', 'total_livros', 'criado_em']

    @extend_schema_field(serializers.IntegerField)
    def get_total_livros(self, obj):
        if hasattr(obj, 'total_livros'):
            return int(obj.total_livros or 0)
        return obj.livros.filter(ativo=True).count()

    def validate_nome(self, value):
        nome = value.strip()
        if not nome:
            raise serializers.ValidationError(_('O nome da categoria é obrigatório.'))
        qs = Categoria.objects.filter(nome__iexact=nome)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(_('Já existe uma categoria com este nome.'))
        return nome


class AutorResumoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Autor
        fields = ['id', 'nome']


class AutorSerializer(serializers.ModelSerializer):
    total_livros = serializers.SerializerMethodField()

    class Meta:
        model = Autor
        fields = ['id', 'nome', 'nacionalidade', 'biografia', 'total_livros', 'criado_em']
        read_only_fields = ['id', 'total_livros', 'criado_em']

    @extend_schema_field(serializers.IntegerField)
    def get_total_livros(self, obj):
        if hasattr(obj, 'total_livros'):
            return int(obj.total_livros or 0)
        return obj.livros.filter(ativo=True).count()

    def validate_nome(self, value):
        nome = value.strip()
        if not nome:
            raise serializers.ValidationError(_('O nome do autor é obrigatório.'))
        return nome


class EditoraResumoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Editora
        fields = ['id', 'nome']


class EditoraSerializer(serializers.ModelSerializer):
    total_livros = serializers.SerializerMethodField()

    class Meta:
        model = Editora
        fields = ['id', 'nome', 'cidade', 'site', 'total_livros', 'criado_em']
        read_only_fields = ['id', 'total_livros', 'criado_em']

    @extend_schema_field(serializers.IntegerField)
    def get_total_livros(self, obj):
        if hasattr(obj, 'total_livros'):
            return int(obj.total_livros or 0)
        return obj.livros.filter(ativo=True).count()

    def validate_nome(self, value):
        nome = value.strip()
        if not nome:
            raise serializers.ValidationError(_('O nome da editora é obrigatório.'))
        qs = Editora.objects.filter(nome__iexact=nome)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(_('Já existe uma editora com este nome.'))
        return nome


class EmprestimoResumoLivroSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    dias_restantes = serializers.IntegerField(read_only=True)
    pode_ler = serializers.BooleanField(read_only=True)

    class Meta:
        model = Emprestimo
        fields = [
            'id',
            'status',
            'status_display',
            'data_emprestimo',
            'data_prevista_devolucao',
            'dias_restantes',
            'renovacoes',
            'pode_ler',
        ]


class AvaliacaoSerializer(serializers.ModelSerializer):
    usuario_id = serializers.UUIDField(source='usuario.id', read_only=True)
    usuario_nome = serializers.CharField(source='usuario.nome', read_only=True)
    usuario_turma = serializers.SerializerMethodField()

    class Meta:
        model = Avaliacao
        fields = [
            'id',
            'usuario_id',
            'usuario_nome',
            'usuario_turma',
            'nota',
            'comentario',
            'criado_em',
            'atualizado_em',
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_usuario_turma(self, obj):
        turma = getattr(obj.usuario, 'turma', None)
        return turma.nome if turma is not None else None


class AvaliacaoCreateUpdateSerializer(serializers.Serializer):
    nota = serializers.IntegerField(min_value=1, max_value=5)
    comentario = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=2000,
    )

    def validate_comentario(self, value):
        if value is None:
            return None
        texto = value.strip()
        return texto or None


class LivroListSerializer(serializers.ModelSerializer):
    """Serializer de listagem do catálogo — nunca expõe a URL direta do arquivo privado."""

    autores = AutorResumoSerializer(many=True, read_only=True)
    categoria = CategoriaResumoSerializer(read_only=True)
    editora = EditoraResumoSerializer(read_only=True)
    formato_display = serializers.CharField(source='get_formato_display', read_only=True)
    disponivel = serializers.BooleanField(read_only=True)
    possui_arquivo = serializers.BooleanField(read_only=True)
    possui_pdf = serializers.BooleanField(read_only=True)
    nome_arquivo = serializers.SerializerMethodField()
    tamanho_arquivo = serializers.SerializerMethodField()
    nota_media = serializers.SerializerMethodField()
    total_avaliacoes = serializers.SerializerMethodField()
    total_acessos = serializers.SerializerMethodField()
    meu_emprestimo = serializers.SerializerMethodField()

    class Meta:
        model = Livro
        fields = [
            'id',
            'titulo',
            'autores',
            'categoria',
            'editora',
            'isbn',
            'ano_publicacao',
            'capa',
            'formato',
            'formato_display',
            'possui_arquivo',
            'possui_pdf',
            'nome_arquivo',
            'tamanho_arquivo',
            'quantidade_total',
            'quantidade_disponivel',
            'disponivel',
            'dominio_publico',
            'ativo',
            'nota_media',
            'total_avaliacoes',
            'total_acessos',
            'meu_emprestimo',
            'criado_em',
        ]
        read_only_fields = fields

    def _obter_emprestimo_aberto_usuario(self, obj):
        if hasattr(obj, 'emprestimos_abertos_usuario'):
            lista = obj.emprestimos_abertos_usuario
            return lista[0] if lista else None

        request = self.context.get('request')
        perfil = obter_perfil_usuario(getattr(request, 'user', None)) if request else None
        if perfil is None:
            return None

        return (
            Emprestimo.objects.filter(
                livro=obj,
                usuario=perfil,
                status__in=[Emprestimo.STATUS_ATIVO, Emprestimo.STATUS_ATRASADO],
            )
            .order_by('-data_emprestimo')
            .first()
        )

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_nome_arquivo(self, obj):
        if not obj.arquivo_pdf or not obj.arquivo_pdf.name:
            return None
        return os.path.basename(obj.arquivo_pdf.name)

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_tamanho_arquivo(self, obj):
        if not obj.arquivo_pdf or not obj.arquivo_pdf.name:
            return None
        try:
            return obj.arquivo_pdf.size
        except (OSError, ValueError):
            return None

    @extend_schema_field(serializers.FloatField(allow_null=True))
    def get_nota_media(self, obj):
        media = getattr(obj, 'nota_media', None)
        if media is None:
            return None
        return round(float(media), 2)

    @extend_schema_field(serializers.IntegerField)
    def get_total_avaliacoes(self, obj):
        if hasattr(obj, 'total_avaliacoes'):
            return int(obj.total_avaliacoes or 0)
        return obj.avaliacoes.count()

    @extend_schema_field(serializers.IntegerField)
    def get_total_acessos(self, obj):
        if hasattr(obj, 'total_acessos'):
            return int(obj.total_acessos or 0)
        return obj.registros_acesso.count()

    @extend_schema_field(EmprestimoResumoLivroSerializer(allow_null=True))
    def get_meu_emprestimo(self, obj):
        emprestimo = self._obter_emprestimo_aberto_usuario(obj)
        if emprestimo is None:
            return None
        return EmprestimoResumoLivroSerializer(emprestimo).data


class LivroDetailSerializer(LivroListSerializer):
    """Detalhes completos da obra no catálogo com permissões calculadas de leitura e download."""

    cadastrado_por_nome = serializers.SerializerMethodField()
    pode_ler = serializers.SerializerMethodField()
    pode_baixar = serializers.SerializerMethodField()
    minha_avaliacao = serializers.SerializerMethodField()

    class Meta(LivroListSerializer.Meta):
        fields = LivroListSerializer.Meta.fields + [
            'sinopse',
            'cadastrado_por_nome',
            'pode_ler',
            'pode_baixar',
            'minha_avaliacao',
            'atualizado_em',
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_cadastrado_por_nome(self, obj):
        if obj.cadastrado_por is None:
            return None
        return obj.cadastrado_por.nome

    @extend_schema_field(serializers.BooleanField)
    def get_pode_baixar(self, obj):
        return bool(obj.pode_baixar_direto)

    @extend_schema_field(serializers.BooleanField)
    def get_pode_ler(self, obj):
        if not obj.ativo or not obj.possui_pdf:
            return False
        if obj.dominio_publico:
            return True

        request = self.context.get('request')
        user = getattr(request, 'user', None) if request else None
        if user is not None and (user.is_superuser or user.is_staff):
            return True

        perfil = obter_perfil_usuario(user) if user else None
        if perfil is not None and perfil.eh_bibliotecario:
            return True

        emprestimo = self._obter_emprestimo_aberto_usuario(obj)
        return bool(emprestimo and emprestimo.pode_ler)

    @extend_schema_field(AvaliacaoSerializer(allow_null=True))
    def get_minha_avaliacao(self, obj):
        if hasattr(obj, 'avaliacoes_usuario'):
            lista = obj.avaliacoes_usuario
            avaliacao = lista[0] if lista else None
        else:
            request = self.context.get('request')
            perfil = obter_perfil_usuario(getattr(request, 'user', None)) if request else None
            if perfil is None:
                return None
            avaliacao = (
                Avaliacao.objects.select_related('usuario', 'usuario__turma')
                .filter(livro=obj, usuario=perfil)
                .first()
            )

        if avaliacao is None:
            return None
        return AvaliacaoSerializer(avaliacao).data
