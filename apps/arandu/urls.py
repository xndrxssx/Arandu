from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AutorViewSet,
    CategoriaViewSet,
    EditoraViewSet,
    LivroCatalogoViewSet,
)

router = DefaultRouter()
router.register(r'livros', LivroCatalogoViewSet, basename='catalogo-livros')
router.register(r'categorias', CategoriaViewSet, basename='catalogo-categorias')
router.register(r'autores', AutorViewSet, basename='catalogo-autores')
router.register(r'editoras', EditoraViewSet, basename='catalogo-editoras')

urlpatterns = [
    path('', include(router.urls)),
]
