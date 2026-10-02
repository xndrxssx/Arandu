# Arandu - Saber Digital 📚

> **Sistema de Agendamento e Gestão de Biblioteca**  
> Projeto desenvolvido para atender a uma demanda real do **Colégio Estadual de Tempo Integral Paulo José de Oliveira**.

---

## 👥 Integrantes da Equipe

* **Francisco Sérgio Feitosa Lima Segundo** (Líder do Grupo)
* **Andressa Luíza Carvalho de Costa**
* **Adhemar Cavalcanti**
* **Hanah Silva e Siqueira**

---

## 📖 Sobre o Projeto

O **Arandu - Saber Digital** é uma plataforma centralizada para a biblioteca escolar onde a instituição de ensino realiza a catalogação e o upload de livros digitais (PDFs e e-books), e os alunos podem pesquisar o catálogo, solicitar empréstimos/aluguéis e fazer download das obras literárias e acadêmicas.

### Principais Funcionalidades:
- **Gestão de Usuários:** Cadastro de alunos e administradores com matrículas e controle de acesso.
- **Catálogo de Livros:** Cadastro completo com título, autor, ISBN, sinopse e categorias com chaves UUID universais.
- **Upload & Armazenamento Digital:** Armazenamento de arquivos digitais para download.
- **Controle de Empréstimos:** Gestão de prazos de entrega, devoluções e status (Ativo, Devolvido, Atrasado).
- **Django Admin Customizado:** Interface administrativa com relações de dependência via *Inlines*, filtros avançados e busca textual.
- **Povoamento Automatizado (Faker):** Comando para gerar centenas de registros de teste com dados brasileiros realistas.

---

## 🛠️ Tecnologias Utilizadas

* **Python 3.8**
* **Django 3.2**
* **Docker & Docker Compose** (Containerização com suporte a recarga em tempo real)
* **SQLite3** (Banco de dados relacional com UUID)
* **Faker** (Geração de dados sintéticos para testes)
* **debugpy** (Depuração remota integrada ao VS Code)

---

## 🚀 Como Executar o Projeto

### Pré-requisitos:
* [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalado e em execução.

### Passo a passo:

1. **Clone o repositório:**
   ```bash
   git clone https://github.com/xndrxssx/Arandu-Saber-Digital.git
   cd Arandu-Saber-Digital
   ```

2. **Inicie o ambiente com o Docker Compose:**
   ```bash
   docker compose up
   ```

3. **Acesse a aplicação:**
   * **Servidor Web:** [http://localhost:8000](http://localhost:8000)
   * **Painel Administrativo:** [http://localhost:8000/admin/](http://localhost:8000/admin/)

---

## 🔑 Credenciais de Acesso (Django Admin)

* **URL:** `http://localhost:8000/admin/`
* **Usuário:** `admin`
* **Senha:** `admindsw`

*(As credenciais também estão descritas no arquivo `credenciais.txt`)*

---

## 🎲 Povoar o Banco com Dados Fake

O banco de dados já vem populado com quase 500 registros. Se desejar gerar novos dados a qualquer momento, execute:

```bash
docker compose exec web python manage.py popular_banco
```
