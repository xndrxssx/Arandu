from django.urls import path
from . import views

app_name = 'arandu'

urlpatterns = [
    path('', views.registrar_emprestimo, name='index'),
    path('emprestimos/novo/', views.registrar_emprestimo, name='registrar_emprestimo'),
]
