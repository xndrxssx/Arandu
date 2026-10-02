from django.contrib import admin
from .models import Categoria, Usuario, Livro, Emprestimo


class LivroInline(admin.TabularInline):
    model = Livro
    extra = 0
    fields = ('titulo', 'autor', 'ano_publicacao', 'quantidade_disponivel')
    show_change_link = True


class EmprestimoUsuarioInline(admin.TabularInline):
    model = Emprestimo
    extra = 0
    fields = ('livro', 'data_emprestimo', 'data_prevista_devolucao', 'status')
    readonly_fields = ('data_emprestimo',)
    show_change_link = True


class EmprestimoLivroInline(admin.TabularInline):
    model = Emprestimo
    extra = 0
    fields = ('usuario', 'data_emprestimo', 'data_prevista_devolucao', 'status')
    readonly_fields = ('data_emprestimo',)
    show_change_link = True


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'descricao', 'data_criacao')
    search_fields = ('nome', 'descricao')
    inlines = [LivroInline]

@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ('nome', 'matricula', 'email', 'tipo', 'ativo', 'data_cadastro')
    list_filter = ('tipo', 'ativo', 'data_cadastro')
    search_fields = ('nome', 'matricula', 'email', 'telefone')
    list_editable = ('ativo',)
    inlines = [EmprestimoUsuarioInline]

@admin.register(Livro)
class LivroAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'autor', 'categoria', 'ano_publicacao', 'quantidade_disponivel', 'arquivo_digital')
    list_filter = ('categoria', 'ano_publicacao', 'data_cadastro')
    search_fields = ('titulo', 'autor', 'isbn', 'sinopse')
    inlines = [EmprestimoLivroInline]

@admin.register(Emprestimo)
class EmprestimoAdmin(admin.ModelAdmin):
    list_display = ('livro', 'usuario', 'data_emprestimo', 'data_prevista_devolucao', 'data_devolucao', 'status')
    list_filter = ('status', 'data_emprestimo', 'data_prevista_devolucao')
    search_fields = ('livro__titulo', 'usuario__nome', 'usuario__matricula')
    date_hierarchy = 'data_emprestimo'
    autocomplete_fields = ['livro', 'usuario']
