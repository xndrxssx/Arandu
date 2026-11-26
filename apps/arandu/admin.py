from django.contrib import admin

from .models import (
    Autor,
    Avaliacao,
    Categoria,
    Editora,
    Emprestimo,
    Livro,
    RegistroAcesso,
)


class LivroInline(admin.TabularInline):
    model = Livro
    extra = 0
    fields = ('titulo', 'ano_publicacao', 'quantidade_disponivel', 'quantidade_total', 'ativo')
    show_change_link = True


class EmprestimoLivroInline(admin.TabularInline):
    model = Emprestimo
    extra = 0
    fields = ('usuario', 'data_emprestimo', 'data_prevista_devolucao', 'status')
    readonly_fields = ('data_emprestimo',)
    show_change_link = True


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'slug', 'criado_em')
    search_fields = ('nome', 'descricao')
    prepopulated_fields = {'slug': ('nome',)}
    inlines = [LivroInline]


@admin.register(Autor)
class AutorAdmin(admin.ModelAdmin):
    list_display = ('nome', 'nacionalidade', 'criado_em')
    search_fields = ('nome', 'nacionalidade')


@admin.register(Editora)
class EditoraAdmin(admin.ModelAdmin):
    list_display = ('nome', 'cidade', 'site', 'criado_em')
    search_fields = ('nome', 'cidade')


@admin.register(Livro)
class LivroAdmin(admin.ModelAdmin):
    list_display = (
        'titulo',
        'categoria',
        'editora',
        'ano_publicacao',
        'quantidade_disponivel',
        'quantidade_total',
        'dominio_publico',
        'ativo',
    )
    list_filter = ('categoria', 'dominio_publico', 'ativo', 'ano_publicacao', 'criado_em')
    search_fields = ('titulo', 'autores__nome', 'isbn', 'sinopse')
    autocomplete_fields = ['categoria', 'editora', 'autores', 'cadastrado_por']
    inlines = [EmprestimoLivroInline]


@admin.register(Emprestimo)
class EmprestimoAdmin(admin.ModelAdmin):
    list_display = (
        'livro',
        'usuario',
        'data_emprestimo',
        'data_prevista_devolucao',
        'data_devolucao',
        'status',
        'renovacoes',
    )
    list_filter = ('status', 'data_emprestimo', 'data_prevista_devolucao')
    search_fields = ('livro__titulo', 'livro__isbn', 'usuario__nome', 'usuario__matricula')
    date_hierarchy = 'data_emprestimo'
    autocomplete_fields = ['livro', 'usuario']


@admin.register(Avaliacao)
class AvaliacaoAdmin(admin.ModelAdmin):
    list_display = ('livro', 'usuario', 'nota', 'criado_em')
    list_filter = ('nota', 'criado_em')
    search_fields = ('livro__titulo', 'usuario__nome', 'comentario')
    autocomplete_fields = ['livro', 'usuario']


@admin.register(RegistroAcesso)
class RegistroAcessoAdmin(admin.ModelAdmin):
    list_display = ('livro', 'usuario', 'tipo', 'ip', 'acessado_em')
    list_filter = ('tipo', 'acessado_em')
    search_fields = ('livro__titulo', 'usuario__nome', 'ip')
    readonly_fields = ('acessado_em',)
