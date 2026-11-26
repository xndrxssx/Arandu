import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from .validators import validar_matricula


def ano_letivo_atual():
    return timezone.localdate().year


class Turma(models.Model):
    """Turma escolar para agrupamento de alunos do CETI Paulo José de Oliveira."""

    TURNO_MANHA = 'MANHA'
    TURNO_TARDE = 'TARDE'
    TURNO_INTEGRAL = 'INTEGRAL'
    TURNO_CHOICES = [
        (TURNO_MANHA, 'Manhã'),
        (TURNO_TARDE, 'Tarde'),
        (TURNO_INTEGRAL, 'Integral'),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name='ID da Turma',
    )
    nome = models.CharField(
        max_length=80,
        verbose_name='Nome da Turma',
    )
    turno = models.CharField(
        max_length=15,
        choices=TURNO_CHOICES,
        default=TURNO_INTEGRAL,
        verbose_name='Turno',
    )
    ano_letivo = models.PositiveIntegerField(
        default=ano_letivo_atual,
        validators=[MinValueValidator(2000), MaxValueValidator(2100)],
        verbose_name='Ano Letivo',
    )
    ativa = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name='Turma Ativa',
    )
    criado_em = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Criado em',
    )
    atualizado_em = models.DateTimeField(
        auto_now=True,
        verbose_name='Atualizado em',
    )

    class Meta:
        verbose_name = 'Turma'
        verbose_name_plural = 'Turmas'
        ordering = ['-ano_letivo', 'nome']
        constraints = [
            models.UniqueConstraint(
                fields=['nome', 'ano_letivo'],
                name='unique_turma_nome_ano_letivo',
            ),
        ]

    def __str__(self):
        return f'{self.nome} ({self.get_turno_display()} - {self.ano_letivo})'


class PerfilUsuario(models.Model):
    """Perfil de aluno ou bibliotecário vinculado ao User padrão do Django/Allauth."""

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
        validators=[validar_matricula],
        verbose_name='Matrícula',
    )
    tipo = models.CharField(
        max_length=15,
        choices=TIPO_CHOICES,
        default=TIPO_ALUNO,
        verbose_name='Tipo de Usuário',
    )
    turma = models.ForeignKey(
        Turma,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='alunos',
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
        db_index=True,
        verbose_name='Usuário Ativo',
    )
    precisa_trocar_senha = models.BooleanField(
        default=False,
        verbose_name='Precisa Trocar Senha',
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

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        if self.matricula:
            self.matricula = self.matricula.strip()
        super().save(*args, **kwargs)

    @property
    def eh_bibliotecario(self):
        return self.tipo == self.TIPO_BIBLIOTECARIO or bool(
            self.user and (self.user.is_staff or self.user.is_superuser)
        )

    def __str__(self):
        return f'{self.nome} ({self.get_tipo_display()}) - Matrícula: {self.matricula}'
