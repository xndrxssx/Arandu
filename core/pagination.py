from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class AranduPagination(PageNumberPagination):
    """Paginação padrão de todas as listagens da API Arandu."""

    page_size = 12
    page_size_query_param = 'page_size'
    max_page_size = 50

    def get_paginated_response(self, data):
        return Response({
            'count': self.page.paginator.count,
            'total_pages': self.page.paginator.num_pages,
            'current_page': self.page.number,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data,
        })

    def get_paginated_response_schema(self, schema):
        return {
            'type': 'object',
            'required': ['count', 'total_pages', 'current_page', 'results'],
            'properties': {
                'count': {
                    'type': 'integer',
                    'example': 48,
                },
                'total_pages': {
                    'type': 'integer',
                    'example': 4,
                },
                'current_page': {
                    'type': 'integer',
                    'example': 1,
                },
                'next': {
                    'type': 'string',
                    'nullable': True,
                    'format': 'uri',
                    'example': 'http://localhost:8080/api/livros/?page=2',
                },
                'previous': {
                    'type': 'string',
                    'nullable': True,
                    'format': 'uri',
                    'example': None,
                },
                'results': schema,
            },
        }
