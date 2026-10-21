from datetime import timedelta
from django import forms
from django.utils import timezone
from .models import Emprestimo, Livro, Usuario


class EmprestimoForm(forms.ModelForm):
    """Formulário para agendamento e registro de empréstimos de livros."""

    data_prevista_devolucao = forms.DateField(
        label="Previsão de Devolução",
        required=True,
        input_formats=['%Y-%m-%d', '%d/%m/%Y'],
        widget=forms.DateInput(
            format='%Y-%m-%d',
            attrs={
                'type': 'date',
                'class': 'form-control',
            }
        ),
        help_text="Informe uma data a partir de hoje (prazo máximo de 30 dias)."
    )

    class Meta:
        model = Emprestimo
        fields = ['usuario', 'livro', 'data_prevista_devolucao', 'observacoes']
        widgets = {
            'usuario': forms.Select(attrs={'class': 'form-control'}),
            'livro': forms.Select(attrs={'class': 'form-control'}),
            'observacoes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Observações opcionais sobre o empréstimo...'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['usuario'].queryset = Usuario.objects.filter(ativo=True).order_by('nome')
        self.fields['usuario'].empty_label = "Selecione um aluno / usuário"
        self.fields['livro'].queryset = Livro.objects.all().order_by('titulo')
        self.fields['livro'].empty_label = "Selecione um livro do acervo"

    def clean_usuario(self):
        usuario = self.cleaned_data.get('usuario')
        if usuario and not usuario.ativo:
            raise forms.ValidationError(
                "Este usuário encontra-se inativo e não pode realizar empréstimos."
            )
        return usuario

    def clean_livro(self):
        livro = self.cleaned_data.get('livro')
        if livro and livro.quantidade_disponivel <= 0:
            raise forms.ValidationError(
                f'O livro "{livro.titulo}" não possui exemplares disponíveis no momento.'
            )
        return livro

    def clean_data_prevista_devolucao(self):
        data_prevista = self.cleaned_data.get('data_prevista_devolucao')
        if data_prevista:
            hoje = timezone.localdate()
            if data_prevista < hoje:
                raise forms.ValidationError(
                    "A data prevista de devolução não pode ser anterior à data de hoje."
                )
            limite_maximo = hoje + timedelta(days=30)
            if data_prevista > limite_maximo:
                raise forms.ValidationError(
                    "O prazo máximo para devolução é de 30 dias a partir da data atual."
                )
        return data_prevista
