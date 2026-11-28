import uuid

import django_filters
from django.db.models import Q

from .models import Livro


class LivroFilter(django_filters.FilterSet):
    """Filtros do catálogo de livros (categoria por UUID ou slug, acesso, disponibilidade e formato)."""

    categoria = django_filters.CharFilter(
        method='filter_categoria',
        help_text='Filtra por UUID, slug ou nome da categoria.',
    )
    dominio_publico = django_filters.BooleanFilter(
        field_name='dominio_publico',
        help_text='Filtra obras em domínio público (true) ou aluguel temporário (false).',
    )
    disponivel = django_filters.BooleanFilter(
        method='filter_disponivel',
        help_text='Filtra obras disponíveis para acesso/empréstimo imediato.',
    )
    formato = django_filters.CharFilter(
        field_name='formato',
        lookup_expr='iexact',
        help_text='Filtra por formato do arquivo digital (PDF ou EPUB).',
    )
    autor = django_filters.UUIDFilter(
        field_name='autores__id',
        help_text='Filtra por UUID de um autor.',
    )
    editora = django_filters.UUIDFilter(
        field_name='editora_id',
        help_text='Filtra por UUID da editora.',
    )
    ano_publicacao = django_filters.NumberFilter(
        field_name='ano_publicacao',
        help_text='Filtra pelo ano exato de publicação.',
    )

    class Meta:
        model = Livro
        fields = [
            'categoria',
            'dominio_publico',
            'disponivel',
            'formato',
            'autor',
            'editora',
            'ano_publicacao',
        ]

    def filter_categoria(self, queryset, name, value):
        valor = (value or '').strip()
        if not valor:
            return queryset

        try:
            categoria_uuid = uuid.UUID(valor)
        except (ValueError, TypeError):
            return queryset.filter(
                Q(categoria__slug__iexact=valor) | Q(categoria__nome__iexact=valor)
            )
        return queryset.filter(categoria_id=categoria_uuid)

    def filter_disponivel(self, queryset, name, value):
        if value is True:
            return queryset.filter(Q(dominio_publico=True) | Q(quantidade_disponivel__gt=0))
        if value is False:
            return queryset.filter(dominio_publico=False, quantidade_disponivel=0)
        return queryset
