from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AutorViewSet,
    CategoriaViewSet,
    EditoraViewSet,
    GestaoResumoView,
    LivroCatalogoViewSet,
    LivroGestaoViewSet,
)

router = DefaultRouter()
router.register(r'livros', LivroCatalogoViewSet, basename='catalogo-livros')
router.register(r'categorias', CategoriaViewSet, basename='catalogo-categorias')
router.register(r'autores', AutorViewSet, basename='catalogo-autores')
router.register(r'editoras', EditoraViewSet, basename='catalogo-editoras')
router.register(r'gestao/livros', LivroGestaoViewSet, basename='gestao-livros')

urlpatterns = [
    path('gestao/resumo/', GestaoResumoView.as_view(), name='gestao-resumo'),
    path('', include(router.urls)),
]
