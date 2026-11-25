from django.contrib import admin

from .models import Categoria, Emprestimo, Livro, PerfilUsuario


class LivroInline(admin.TabularInline):
    model = Livro
    extra = 0
    fields = ('titulo', 'autor', 'ano_publicacao', 'quantidade_disponivel', 'quantidade_total')
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
    list_display = ('nome', 'slug', 'criado_em')
    search_fields = ('nome', 'descricao')
    prepopulated_fields = {'slug': ('nome',)}
    inlines = [LivroInline]


@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ('nome', 'matricula', 'email', 'turma', 'tipo', 'ativo', 'criado_em')
    list_filter = ('tipo', 'ativo', 'turma', 'criado_em')
    search_fields = ('nome', 'matricula', 'email', 'turma', 'telefone')
    list_editable = ('ativo',)
    inlines = [EmprestimoUsuarioInline]


@admin.register(Livro)
class LivroAdmin(admin.ModelAdmin):
    list_display = (
        'titulo',
        'autor',
        'categoria',
        'ano_publicacao',
        'quantidade_disponivel',
        'quantidade_total',
        'dominio_publico',
        'arquivo_pdf',
    )
    list_filter = ('categoria', 'dominio_publico', 'ano_publicacao', 'criado_em')
    search_fields = ('titulo', 'autor', 'isbn', 'sinopse')
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
