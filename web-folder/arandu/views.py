from django.contrib import messages
from django.shortcuts import redirect, render
from .forms import EmprestimoForm
from .models import Emprestimo


def registrar_emprestimo(request):
    """View para agendamento e registro de empréstimo de livros com validação e PRG."""
    if request.method == 'POST':
        form = EmprestimoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                'Empréstimo registrado com sucesso no sistema!'
            )
            return redirect('arandu:registrar_emprestimo')
        else:
            messages.error(
                request,
                'Erro na validação do formulário. Verifique os campos destacados abaixo e tente novamente.'
            )
    else:
        form = EmprestimoForm()

    ultimos_emprestimos = Emprestimo.objects.select_related('usuario', 'livro').order_by('-data_emprestimo')[:10]

    context = {
        'form': form,
        'ultimos_emprestimos': ultimos_emprestimos,
    }
    return render(request, 'arandu/emprestimo_form.html', context)
