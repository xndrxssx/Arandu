from django.db import models
from django.utils import timezone
import uuid

class Categoria(models.Model):
    """Modelo para representar uma categoria de livros."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, verbose_name='ID da Categoria')
    nome = models.CharField(max_length=100, unique=True, verbose_name='Nome da Categoria')
    descricao = models.TextField(blank=True, null=True, verbose_name='Descrição da Categoria')
    data_criacao = models.DateTimeField(default=timezone.now, verbose_name='Data de Criação')
    
    class Meta:
        verbose_name = 'Categoria'
        verbose_name_plural = 'Categorias'
        ordering = ['nome']

    def __str__(self):
        return self.nome

class Usuario(models.Model):
    """Modelo para representar um usuário do sistema."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, verbose_name='ID do Usuário')
    TIPO_CHOICES = [
        ('ALUNO', 'Aluno'),
        ('ADMIN', 'Administrador'),
    ]

    nome = models.CharField(max_length=150, verbose_name='Nome Completo')
    email = models.EmailField(unique=True, verbose_name='E-mail do Usuário')
    matricula = models.CharField(max_length=30, unique=True, verbose_name='Matrícula do Usuário')
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, default='ALUNO', verbose_name='Tipo de Usuário')
    telefone = models.CharField(max_length=20, blank=True, null=True, verbose_name='Telefone do Usuário')
    ativo = models.BooleanField(default=True, verbose_name='Usuário Ativo')
    data_cadastro = models.DateTimeField(auto_now_add=True, verbose_name='Data de Cadastro')
    
    
    class Meta:
        verbose_name = 'Usuário'
        verbose_name_plural = 'Usuários'
        ordering = ['nome']

    def __str__(self):
        return f"{self.nome} ({self.get_tipo_display()}) - Matrícula: {self.matricula}"
    
class Livro(models.Model):
    """Modelo para representar um livro na biblioteca."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, verbose_name="ID do Livro")
    titulo = models.CharField(max_length=200, verbose_name="Título")
    autor = models.CharField(max_length=150, verbose_name="Autor")
    isbn = models.CharField(max_length=20, unique=True, verbose_name="ISBN")
    ano_publicacao = models.PositiveIntegerField(verbose_name="Ano de Publicação")
    sinopse = models.TextField(blank=True, null=True, verbose_name="Sinopse")
    
    # Relação com Categoria: Se a categoria for apagada, protegemos os livros (models.PROTECT)
    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.PROTECT,
        related_name="livros",
        verbose_name="Categoria"
    )
    
    # Upload do livro digital (PDF/e-book) para os alunos baixarem
    arquivo_digital = models.FileField(
        upload_to="livros/digitais/",
        blank=True,
        null=True,
        verbose_name="Arquivo Digital (PDF/E-book)"
    )
    
    quantidade_disponivel = models.PositiveIntegerField(default=1, verbose_name="Quantidade de Exemplares")
    data_cadastro = models.DateTimeField(auto_now_add=True, verbose_name="Cadastrado em")
    
    class Meta:
        verbose_name = 'Livro'
        verbose_name_plural = 'Livros'
        ordering = ['titulo']

    def __str__(self):
        return f"{self.titulo} - {self.autor}"
    
class Emprestimo(models.Model):
    """Modelo para representar um empréstimo de livro por um usuário."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, verbose_name="ID do Empréstimo")
    STATUS_CHOICES = [
        ('ATIVO', 'Em Andamento'),
        ('DEVOLVIDO', 'Devolvido'),
        ('ATRASADO', 'Atrasado'),
    ]
    
    # Relações de dependência: conecta quem pegou (Usuario) com o que pegou (Livro)
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name="emprestimos",
        verbose_name="Aluno / Usuário"
    )
    
    livro = models.ForeignKey(
        Livro,
        on_delete=models.CASCADE,
        related_name="emprestimos",
        verbose_name="Livro"
    )
    
    data_emprestimo = models.DateTimeField(default=timezone.now, verbose_name="Data do Empréstimo")
    data_prevista_devolucao = models.DateField(verbose_name="Previsão de Devolução")
    data_devolucao = models.DateField(blank=True, null=True, verbose_name="Devolvido em")
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='ATIVO', verbose_name="Status")
    observacoes = models.TextField(blank=True, null=True, verbose_name="Observações")
    
    class Meta:
        verbose_name = "Empréstimo"
        verbose_name_plural = "Empréstimos"
        ordering = ['-data_emprestimo']
    
    def __str__(self):
        return f"{self.livro.titulo} alugado por {self.usuario.nome} ({self.get_status_display()})"