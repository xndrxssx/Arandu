import random
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from faker import Faker
from arandu.models import Categoria, Usuario, Livro, Emprestimo


class Command(BaseCommand):
    help = 'Popula o banco de dados com centenas de registros fake usando a biblioteca Faker'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('>>> Iniciando o povoamento do banco de dados do Saber Digital...'))
        fake = Faker('pt_BR')

        categorias_dados = [
            ("Literatura Brasileira", "Obras clássicas e contemporâneas de autores nacionais."),
            ("Ficção Científica", "Explorações espaciais, distopias, viagens no tempo e futuros imaginados."),
            ("História Geral e do Brasil", "Estudos históricos, movimentos sociais e eventos marcantes."),
            ("Ciências da Natureza e Biologia", "Ecologia, genética, botânica e ciências ambientais."),
            ("Matemática e Raciocínio Lógico", "Álgebra, geometria, cálculo e desafios lógicos."),
            ("Filosofia e Sociologia", "Pensamento crítico, correntes filosóficas e estudos da sociedade."),
            ("Geografia e Geopolítica", "Cartografia, relevo, clima e relações geopolíticas mundiais."),
            ("Física e Astronomia", "Mecânica, termodinâmica, física quântica e astronomia."),
            ("Química e Materiais", "Química orgânica, inorgânica, reações e processos químicos."),
            ("Histórias em Quadrinhos e Mangás", "Narrativas gráficas, graphic novels e mangás."),
            ("Poesia e Crônicas", "Antologias poéticas, versos livres e crônicas do cotidiano."),
            ("Tecnologia e Computação", "Algoritmos, programação, redes e inteligência artificial.")
        ]

        categorias_objs = []
        for nome, desc in categorias_dados:
            cat, _ = Categoria.objects.get_or_create(
                nome=nome,
                defaults={'descricao': desc}
            )
            categorias_objs.append(cat)

        self.stdout.write(self.style.SUCCESS(f'[OK] {len(categorias_objs)} categorias cadastradas/verificadas.'))

        total_usuarios_para_criar = 120
        usuarios_criados = 0
        matriculas_usadas = set(Usuario.objects.values_list('matricula', flat=True))
        emails_usados = set(Usuario.objects.values_list('email', flat=True))

        for i in range(1, total_usuarios_para_criar + 1):
            matricula = f"2026{str(i).zfill(5)}"
            while matricula in matriculas_usadas:
                matricula = f"2026{random.randint(10000, 99999)}"
            matriculas_usadas.add(matricula)

            nome = fake.name()
            email_base = fake.user_name()
            email = f"{email_base}_{random.randint(10, 9999)}@colegiopaulo.edu.br"
            while email in emails_usados:
                email = f"{email_base}_{random.randint(1000, 999999)}@colegiopaulo.edu.br"
            emails_usados.add(email)

            tipo = 'ADMIN' if random.random() < 0.1 else 'ALUNO'

            Usuario.objects.create(
                nome=nome,
                email=email,
                matricula=matricula,
                tipo=tipo,
                telefone=fake.phone_number()[:20],
                ativo=fake.boolean(chance_of_getting_true=95)
            )
            usuarios_criados += 1

        self.stdout.write(self.style.SUCCESS(f'[OK] {usuarios_criados} usuários (alunos e admins) criados.'))

        titulos_base = [
            "Dom Casmurro", "Memórias Póstumas de Brás Cubas", "Grande Sertão: Veredas",
            "Vidas Secas", "O Cortiço", "A Hora da Estrela", "Capitães da Areia",
            "Macunaíma", "Quincas Borba", "Iracema", "Senhora", "O Quinze",
            "Auto da Compadecida", "Claro Enigma", "A Rosa do Povo", "Sagarana",
            "Morte e Vida Severina", "O Guarani", "Triste Fim de Policarpo Quaresma",
            "Fundação", "Duna", "Neuromancer", "Fahrenheit 451", "Admirável Mundo Novo",
            "1984", "Cosmos", "Uma Breve História do Tempo", "O Gene Egoísta",
            "O Andar do Bêbado", "Sapiens: Uma Breve História da Humanidade",
            "Homo Deus", "Cálculo Volume 1", "Álgebra Linear e Suas Aplicações",
            "Fundamentos da Física", "Química: A Ciência Central", "Biologia de Campbell",
            "Os Sertões", "Casa-Grande & Senzala", "Raízes do Brasil"
        ]

        total_livros_para_criar = 150
        livros_criados = 0
        isbns_usados = set(Livro.objects.values_list('isbn', flat=True))

        for i in range(total_livros_para_criar):
            if i < len(titulos_base):
                titulo = titulos_base[i]
            else:
                titulo = f"{fake.catch_phrase().title()} (Vol. {random.randint(1, 5)})"

            autor = fake.name()
            
            isbn = fake.isbn13()
            while isbn in isbns_usados:
                isbn = fake.isbn13()
            isbns_usados.add(isbn)

            ano = random.randint(1950, 2026)
            sinopse = fake.paragraph(nb_sentences=random.randint(3, 7))
            categoria = random.choice(categorias_objs)
            qtd = random.randint(1, 8)

            Livro.objects.create(
                titulo=titulo,
                autor=autor,
                isbn=isbn,
                ano_publicacao=ano,
                sinopse=sinopse,
                categoria=categoria,
                quantidade_disponivel=qtd
            )
            livros_criados += 1

        self.stdout.write(self.style.SUCCESS(f'[OK] {livros_criados} livros cadastrados.'))

        todos_usuarios = list(Usuario.objects.filter(tipo='ALUNO'))
        todos_livros = list(Livro.objects.all())
        total_emprestimos_para_criar = 200
        emprestimos_criados = 0
        agora = timezone.now()

        for _ in range(total_emprestimos_para_criar):
            usuario = random.choice(todos_usuarios)
            livro = random.choice(todos_livros)

            dias_atras = random.randint(1, 90)
            data_emp = agora - timedelta(days=dias_atras)

            data_prev = data_emp.date() + timedelta(days=14)

            sorteio = random.random()
            if sorteio < 0.60:
                status = 'DEVOLVIDO'
                dias_para_devolver = random.randint(3, 16)
                data_dev = data_emp.date() + timedelta(days=dias_para_devolver)
                obs = "Livro devolvido em perfeito estado de conservação."
            elif sorteio < 0.85:
                status = 'ATIVO'
                data_dev = None
                obs = "Empréstimo em andamento pelo aluno."
            else:
                status = 'ATRASADO'
                data_dev = None
                obs = "Prazo expirado. Aluno notificado pela coordenação da biblioteca."

            Emprestimo.objects.create(
                usuario=usuario,
                livro=livro,
                data_emprestimo=data_emp,
                data_prevista_devolucao=data_prev,
                data_devolucao=data_dev,
                status=status,
                observacoes=obs
            )
            emprestimos_criados += 1

        self.stdout.write(self.style.SUCCESS(f'[OK] {emprestimos_criados} empréstimos registrados com sucesso!'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS(' BANCO DE DADOS POPULADO COM CENTENAS DE REGISTROS COM SUCESSO!'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
