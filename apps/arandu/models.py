import uuid

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from .storage import private_storage
from .validators import validar_arquivo_pdf, validar_isbn, validar_nota


class Categoria(models.Model):
    """Categoria temática para organização do acervo escolar."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name='ID da Categoria',
    )
    nome = models.CharField(
        max_length=100,
        unique=True,
        verbose_name='Nome da Categoria',
    )
    slug = models.SlugField(
        max_length=120,
        unique=True,
        blank=True,
        verbose_name='Slug',
    )
    descricao = models.TextField(
        blank=True,
        null=True,
        verbose_name='Descrição',
    )
    criado_em = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Criado em',
    )

    class Meta:
        verbose_name = 'Categoria'
        verbose_name_plural = 'Categorias'
        ordering = ['nome']

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.nome) or 'categoria'
            slug = base_slug
            contador = 1
            while Categoria.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base_slug}-{contador}'
                contador += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nome


class Autor(models.Model):
    """Autor de obras catalogadas no acervo."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name='ID do Autor',
    )
    nome = models.CharField(
        max_length=150,
        db_index=True,
        verbose_name='Nome do Autor',
    )
    nacionalidade = models.CharField(
        max_length=80,
        blank=True,
        null=True,
        verbose_name='Nacionalidade',
    )
    biografia = models.TextField(
        blank=True,
        null=True,
        verbose_name='Biografia',
    )
    criado_em = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Cadastrado em',
    )

    class Meta:
        verbose_name = 'Autor'
        verbose_name_plural = 'Autores'
        ordering = ['nome']

    def __str__(self):
        return self.nome


class Editora(models.Model):
    """Editora ou selo institucional responsável pela publicação da obra."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name='ID da Editora',
    )
    nome = models.CharField(
        max_length=150,
        unique=True,
        verbose_name='Nome da Editora',
    )
    cidade = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Cidade',
    )
    site = models.URLField(
        blank=True,
        null=True,
        verbose_name='Site',
    )
    criado_em = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Cadastrado em',
    )

    class Meta:
        verbose_name = 'Editora'
        verbose_name_plural = 'Editoras'
        ordering = ['nome']

    def __str__(self):
        return self.nome


class Livro(models.Model):
    """Obra digital catalogada no acervo com controle de licenças/exemplares simultâneos."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name='ID do Livro',
    )
    titulo = models.CharField(
        max_length=200,
        db_index=True,
        verbose_name='Título',
    )
    autores = models.ManyToManyField(
        Autor,
        related_name='livros',
        blank=True,
        verbose_name='Autores',
    )
    editora = models.ForeignKey(
        Editora,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='livros',
        verbose_name='Editora',
    )
    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.PROTECT,
        related_name='livros',
        verbose_name='Categoria',
    )
    isbn = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        unique=True,
        validators=[validar_isbn],
        verbose_name='ISBN',
    )
    ano_publicacao = models.PositiveIntegerField(
        verbose_name='Ano de Publicação',
    )
    sinopse = models.TextField(
        blank=True,
        null=True,
        verbose_name='Sinopse',
    )
    capa = models.ImageField(
        upload_to='capas/',
        blank=True,
        null=True,
        verbose_name='Capa do Livro',
    )
    arquivo_pdf = models.FileField(
        storage=private_storage,
        upload_to='livros/pdfs/',
        blank=True,
        null=True,
        validators=[validar_arquivo_pdf],
        verbose_name='Arquivo Digital (PDF)',
    )
    quantidade_total = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        verbose_name='Total de Exemplares / Licenças',
    )
    quantidade_disponivel = models.PositiveIntegerField(
        default=1,
        verbose_name='Exemplares Disponíveis',
    )
    dominio_publico = models.BooleanField(
        default=False,
        verbose_name='Obra em Domínio Público',
    )
    ativo = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name='Obra Ativa no Catálogo',
    )
    cadastrado_por = models.ForeignKey(
        'contas.PerfilUsuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='livros_cadastrados',
        verbose_name='Cadastrado por',
    )
    criado_em = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Cadastrado em',
    )
    atualizado_em = models.DateTimeField(
        auto_now=True,
        verbose_name='Atualizado em',
    )

    class Meta:
        verbose_name = 'Livro'
        verbose_name_plural = 'Livros'
        ordering = ['titulo']
        constraints = [
            models.CheckConstraint(
                check=Q(quantidade_disponivel__lte=F('quantidade_total')),
                name='livro_disponivel_nao_excede_total',
            ),
            models.CheckConstraint(
                check=Q(quantidade_total__gte=1),
                name='livro_quantidade_total_minimo_1',
            ),
        ]

    def _normalizar_isbn(self):
        if isinstance(self.isbn, str):
            isbn_limpo = self.isbn.strip()
            self.isbn = isbn_limpo or None

    def clean(self):
        super().clean()
        self._normalizar_isbn()

        if self.quantidade_total is not None and self.quantidade_total < 1:
            raise ValidationError({
                'quantidade_total': _('O total de exemplares deve ser pelo menos 1.'),
            })

        if (
            self.quantidade_disponivel is not None
            and self.quantidade_total is not None
            and self.quantidade_disponivel > self.quantidade_total
        ):
            raise ValidationError({
                'quantidade_disponivel': _(
                    'A quantidade disponível não pode ser maior que o total de exemplares.'
                )
            })

        ano_atual = timezone.localdate().year
        if self.ano_publicacao and self.ano_publicacao > ano_atual + 1:
            raise ValidationError({
                'ano_publicacao': _('O ano de publicação não pode estar no futuro.')
            })

    def save(self, *args, **kwargs):
        self._normalizar_isbn()
        super().save(*args, **kwargs)

    @property
    def disponivel(self):
        return self.ativo and self.quantidade_disponivel > 0

    @property
    def possui_pdf(self):
        return bool(self.arquivo_pdf)

    def __str__(self):
        return self.titulo


class Emprestimo(models.Model):
    """Aluguel temporário de uma obra digital por um usuário com controle de prazo."""

    STATUS_ATIVO = 'ATIVO'
    STATUS_DEVOLVIDO = 'DEVOLVIDO'
    STATUS_ATRASADO = 'ATRASADO'
    STATUS_CHOICES = [
        (STATUS_ATIVO, 'Em Andamento'),
        (STATUS_DEVOLVIDO, 'Devolvido'),
        (STATUS_ATRASADO, 'Atrasado'),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name='ID do Empréstimo',
    )
    usuario = models.ForeignKey(
        'contas.PerfilUsuario',
        on_delete=models.PROTECT,
        related_name='emprestimos',
        verbose_name='Aluno / Usuário',
    )
    livro = models.ForeignKey(
        Livro,
        on_delete=models.PROTECT,
        related_name='emprestimos',
        verbose_name='Livro',
    )
    data_emprestimo = models.DateTimeField(
        default=timezone.now,
        verbose_name='Data do Empréstimo',
    )
    data_prevista_devolucao = models.DateField(
        verbose_name='Previsão de Devolução',
    )
    data_devolucao = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Devolvido em',
    )
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default=STATUS_ATIVO,
        db_index=True,
        verbose_name='Status',
    )
    renovacoes = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='Quantidade de Renovações',
    )
    observacoes = models.TextField(
        blank=True,
        null=True,
        verbose_name='Observações',
    )

    class Meta:
        verbose_name = 'Empréstimo'
        verbose_name_plural = 'Empréstimos'
        ordering = ['-data_emprestimo']
        constraints = [
            models.UniqueConstraint(
                fields=['usuario', 'livro'],
                condition=Q(status__in=['ATIVO', 'ATRASADO']),
                name='unique_emprestimo_aberto_por_usuario_livro',
            ),
        ]

    @property
    def esta_vencido(self):
        return (
            self.status == self.STATUS_ATIVO
            and self.data_prevista_devolucao < timezone.localdate()
        )

    @property
    def dias_restantes(self):
        if self.status == self.STATUS_DEVOLVIDO:
            return 0
        return (self.data_prevista_devolucao - timezone.localdate()).days

    @property
    def pode_ler(self):
        return (
            self.status == self.STATUS_ATIVO
            and self.data_prevista_devolucao >= timezone.localdate()
            and self.livro.possui_pdf
        )

    @property
    def pode_baixar(self):
        return self.pode_ler and self.livro.dominio_publico

    def __str__(self):
        return f'{self.livro.titulo} — {self.usuario.nome} ({self.get_status_display()})'


class Avaliacao(models.Model):
    """Avaliação (nota de 1 a 5 e comentário opcional) de um livro por um usuário."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name='ID da Avaliação',
    )
    usuario = models.ForeignKey(
        'contas.PerfilUsuario',
        on_delete=models.CASCADE,
        related_name='avaliacoes',
        verbose_name='Usuário',
    )
    livro = models.ForeignKey(
        Livro,
        on_delete=models.CASCADE,
        related_name='avaliacoes',
        verbose_name='Livro',
    )
    nota = models.PositiveSmallIntegerField(
        validators=[validar_nota],
        verbose_name='Nota (1 a 5)',
    )
    comentario = models.TextField(
        blank=True,
        null=True,
        verbose_name='Comentário',
    )
    criado_em = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Avaliado em',
    )
    atualizado_em = models.DateTimeField(
        auto_now=True,
        verbose_name='Atualizado em',
    )

    class Meta:
        verbose_name = 'Avaliação'
        verbose_name_plural = 'Avaliações'
        ordering = ['-criado_em']
        constraints = [
            models.UniqueConstraint(
                fields=['usuario', 'livro'],
                name='unique_avaliacao_por_usuario_livro',
            ),
            models.CheckConstraint(
                check=Q(nota__gte=1, nota__lte=5),
                name='avaliacao_nota_entre_1_e_5',
            ),
        ]

    def __str__(self):
        return f'{self.livro.titulo} — {self.usuario.nome} ({self.nota}/5)'


class RegistroAcesso(models.Model):
    """Auditoria de leituras na plataforma e downloads de PDF."""

    TIPO_LEITURA = 'LEITURA'
    TIPO_DOWNLOAD = 'DOWNLOAD'
    TIPO_CHOICES = [
        (TIPO_LEITURA, 'Leitura na Plataforma'),
        (TIPO_DOWNLOAD, 'Download do PDF'),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name='ID do Registro',
    )
    usuario = models.ForeignKey(
        'contas.PerfilUsuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='registros_acesso',
        verbose_name='Usuário',
    )
    livro = models.ForeignKey(
        Livro,
        on_delete=models.CASCADE,
        related_name='registros_acesso',
        verbose_name='Livro',
    )
    emprestimo = models.ForeignKey(
        Emprestimo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='registros_acesso',
        verbose_name='Empréstimo',
    )
    tipo = models.CharField(
        max_length=15,
        choices=TIPO_CHOICES,
        db_index=True,
        verbose_name='Tipo de Acesso',
    )
    ip = models.GenericIPAddressField(
        blank=True,
        null=True,
        verbose_name='Endereço IP',
    )
    acessado_em = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name='Acessado em',
    )

    class Meta:
        verbose_name = 'Registro de Acesso'
        verbose_name_plural = 'Registros de Acesso'
        ordering = ['-acessado_em']

    def __str__(self):
        return f'{self.get_tipo_display()} — {self.livro.titulo}'
