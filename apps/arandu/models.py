import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone
from django.utils.text import slugify


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
            base_slug = slugify(self.nome)
            slug = base_slug
            contador = 1
            while Categoria.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base_slug}-{contador}'
                contador += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nome


class PerfilUsuario(models.Model):
    """Perfil de aluno ou bibliotecário vinculado opcionalmente ao User do Django/Allauth."""

    TIPO_ALUNO = 'ALUNO'
    TIPO_BIBLIOTECARIO = 'BIBLIOTECARIO'
    TIPO_CHOICES = [
        (TIPO_ALUNO, 'Aluno'),
        (TIPO_BIBLIOTECARIO, 'Bibliotecário / Administrador'),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name='ID do Usuário',
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='perfil',
        verbose_name='Conta de Acesso (Auth)',
    )
    nome = models.CharField(
        max_length=150,
        verbose_name='Nome Completo',
    )
    email = models.EmailField(
        unique=True,
        verbose_name='E-mail',
    )
    matricula = models.CharField(
        max_length=30,
        unique=True,
        db_index=True,
        verbose_name='Matrícula',
    )
    tipo = models.CharField(
        max_length=15,
        choices=TIPO_CHOICES,
        default=TIPO_ALUNO,
        verbose_name='Tipo de Usuário',
    )
    turma = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name='Turma / Série',
    )
    telefone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name='Telefone',
    )
    ativo = models.BooleanField(
        default=True,
        verbose_name='Usuário Ativo',
    )
    criado_em = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Data de Cadastro',
    )
    atualizado_em = models.DateTimeField(
        auto_now=True,
        verbose_name='Atualizado em',
    )

    class Meta:
        verbose_name = 'Perfil de Usuário'
        verbose_name_plural = 'Perfis de Usuários'
        ordering = ['nome']

    @property
    def eh_bibliotecario(self):
        return self.tipo == self.TIPO_BIBLIOTECARIO or bool(
            self.user and (self.user.is_staff or self.user.is_superuser)
        )

    def __str__(self):
        return f'{self.nome} ({self.get_tipo_display()}) - Matrícula: {self.matricula}'


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
    autor = models.CharField(
        max_length=150,
        db_index=True,
        verbose_name='Autor',
    )
    isbn = models.CharField(
        max_length=20,
        unique=True,
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
    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.PROTECT,
        related_name='livros',
        verbose_name='Categoria',
    )
    capa = models.ImageField(
        upload_to='livros/capas/',
        blank=True,
        null=True,
        verbose_name='Capa do Livro',
    )
    arquivo_pdf = models.FileField(
        upload_to='livros/pdfs/',
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=['pdf'])],
        verbose_name='Arquivo Digital (PDF)',
    )
    quantidade_total = models.PositiveIntegerField(
        default=1,
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
        ]

    def clean(self):
        super().clean()
        if (
            self.quantidade_disponivel is not None
            and self.quantidade_total is not None
            and self.quantidade_disponivel > self.quantidade_total
        ):
            raise ValidationError({
                'quantidade_disponivel': (
                    'A quantidade disponível não pode ser maior que o total de exemplares.'
                )
            })
        ano_atual = timezone.localdate().year
        if self.ano_publicacao and self.ano_publicacao > ano_atual + 1:
            raise ValidationError({
                'ano_publicacao': 'O ano de publicação não pode estar no futuro.'
            })

    @property
    def disponivel(self):
        return self.quantidade_disponivel > 0

    @property
    def possui_pdf(self):
        return bool(self.arquivo_pdf)

    def __str__(self):
        return f'{self.titulo} - {self.autor}'


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
        PerfilUsuario,
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

    def __str__(self):
        return f'{self.livro.titulo} — {self.usuario.nome} ({self.get_status_display()})'
