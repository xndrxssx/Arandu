from django.contrib import admin

from .models import PerfilUsuario, Turma


@admin.register(Turma)
class TurmaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'turno', 'ano_letivo', 'ativa', 'criado_em')
    list_filter = ('turno', 'ano_letivo', 'ativa')
    search_fields = ('nome',)


@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ('nome', 'matricula', 'email', 'turma', 'tipo', 'ativo', 'precisa_trocar_senha')
    list_filter = ('tipo', 'ativo', 'precisa_trocar_senha', 'turma')
    search_fields = ('nome', 'matricula', 'email', 'telefone')
    list_editable = ('ativo',)
    autocomplete_fields = ['turma']
