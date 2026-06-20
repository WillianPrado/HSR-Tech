# HSR-Tech
Python e IA

## Arquitetura do Projeto

### Visão Geral

O **HSR-Tech** é uma API backend inteligente construída com **FastAPI** para análise de conversas de vendas no WhatsApp. O sistema automatiza a extração, transcrição e análise de mensagens de texto e áudio, gerando relatórios de desempenho de vendas em PDF.

---

### Stack Tecnológica

| Camada | Tecnologias |
|--------|-------------|
| **Web Framework** | FastAPI 0.115+, Uvicorn, Starlette |
| **Banco de Dados** | SQLAlchemy 2.0 (ORM), Alembic (migrations), SQLite / PostgreSQL / MySQL |
| **Autenticação** | JWT (python-jose), bcrypt, passlib |
| **IA / LLM** | OpenAI API (transcrição de áudio e análise) |
| **Filas Assíncronas** | Celery 5.3+, Redis |
| **Geração de Relatórios** | fpdf, pdfkit, weasyprint |
| **Pagamentos** | Stripe |
| **Validação** | Pydantic v2 |
| **Rate Limiting** | slowapi |

---

### Estrutura de Diretórios

```
HSR-Tech/
├── main.py                    # Entrypoint da aplicação FastAPI
├── requirements.txt           # Dependências Python
├── alembic.ini                # Configuração de migrações
│
├── core/                      # Núcleo e utilitários transversais
│   ├── auth.py                # Lógica de autenticação (JWT, hashing)
│   ├── config.py              # Configurações e variáveis de ambiente
│   ├── dependencies.py        # Injeção de dependências do FastAPI
│   ├── exceptions.py          # Exceções customizadas
│   ├── abstractions/          # Classes base abstratas
│   ├── http/                  # Utilitários HTTP
│   ├── storage/               # Handlers de armazenamento de arquivos
│   └── status_tracker.py      # Rastreamento de status de processos
│
├── models/                    # Modelos ORM (SQLAlchemy) – camada de dados
│   ├── user.py                # Usuário e assinaturas
│   ├── conversation.py        # Conversas
│   ├── message.py             # Mensagens individuais
│   └── status_response.py     # Status de processamento
│
├── schemas/                   # Schemas Pydantic (DTOs) – validação e serialização
│   ├── user.py                # UserCreate, UserLogin, UserResponse
│   ├── conversation.py        # ConversationCreate, ConversationResponse
│   ├── auth.py                # Token
│   ├── stripe.py              # Dados de pagamento
│   └── schemas.py             # Schemas gerais
│
├── repository/                # Camada de acesso a dados (padrão Repository)
│   ├── user_repository.py     # CRUD de usuários
│   ├── conversation_repository.py  # CRUD de conversas
│   └── message_repository.py       # CRUD de mensagens
│
├── services/                  # Lógica de negócio
│   ├── db_handler.py          # Inicialização do banco de dados
│   ├── sales_upload.py        # Processamento de upload de arquivos ZIP
│   ├── report_service.py      # Geração de relatórios PDF
│   ├── analysis_service.py    # Análise de vendas
│   ├── conversation_service.py # Gerenciamento de conversas
│   ├── status_service.py      # Rastreamento de status
│   ├── audio/                 # Transcrição de áudio via OpenAI
│   ├── chat/                  # Processamento de chats
│   ├── reports/               # Templates de relatórios
│   ├── sales/                 # Processamento de dados de vendas
│   ├── zip/                   # Extração de arquivos ZIP
│   └── tasks.py               # Tarefas assíncronas (Celery)
│
├── routes/                    # Endpoints da API (FastAPI Routers)
│   ├── auth.py                # POST /auth/register, POST /auth/login
│   ├── sales_upload.py        # POST /upload
│   ├── report_service.py      # GET /report
│   ├── analysis_service.py    # GET /analysis
│   ├── conversation_service.py # GET/POST /conversations
│   └── status_service.py      # GET /status
│
├── alembic/                   # Migrações de banco de dados
│   ├── env.py                 # Ambiente de migração
│   └── versions/              # Arquivos de migration versionados
│
├── prompts/                   # Templates de prompts para IA
├── schemas/                   # (ver acima)
├── scripts/                   # Scripts utilitários
├── public/                    # Arquivos estáticos
└── utils/                     # Funções auxiliares
```

---

### Arquitetura em Camadas

O projeto segue uma arquitetura em camadas inspirada em **Clean Architecture**:

```
┌──────────────────────────────────────────────────┐
│                  routes/                          │  ← Endpoints HTTP (FastAPI Routers)
│  Recebe requisições, valida via Pydantic Schemas  │
└──────────────────────────┬───────────────────────┘
                           │
┌──────────────────────────▼───────────────────────┐
│                 services/                         │  ← Lógica de negócio
│  Orquestra operações, aciona IA, gera relatórios  │
└──────────────────────────┬───────────────────────┘
                           │
┌──────────────────────────▼───────────────────────┐
│                repository/                        │  ← Acesso a dados (CRUD)
│  Interage com os modelos ORM via SQLAlchemy        │
└──────────────────────────┬───────────────────────┘
                           │
┌──────────────────────────▼───────────────────────┐
│                  models/                          │  ← Modelos ORM (SQLAlchemy)
│  Mapeamento objeto-relacional para o banco        │
└──────────────────────────┬───────────────────────┘
                           │
┌──────────────────────────▼───────────────────────┐
│                 Database                          │  ← SQLite / PostgreSQL / MySQL
└──────────────────────────────────────────────────┘
```

**Exemplo de fluxo – Upload de arquivo ZIP:**

```
POST /api/v1/upload  (routes/sales_upload.py)
  ↓
services/sales_upload.py  →  services/zip/  (extração)
                          →  services/audio/ (transcrição via OpenAI)
                          →  services/chat/  (parseamento de mensagens)
  ↓
repository/conversation_repository.py  (salva conversa)
repository/message_repository.py       (salva mensagens)
  ↓
models/conversation.py + models/message.py  (ORM)
  ↓
Database
  ↓ (resposta serializada via)
schemas/conversation.py  (Pydantic ConversationResponse)
```

---

### Endpoints Principais (`/api/v1`)

| Método | Rota | Descrição |
|--------|------|-----------|
| `POST` | `/auth/register` | Cadastro de usuário |
| `POST` | `/auth/login` | Autenticação e geração de JWT |
| `POST` | `/upload` | Upload de ZIP com chats e áudios |
| `GET` | `/report/{id}` | Geração de relatório PDF |
| `GET` | `/analysis/{id}` | Análise de desempenho de vendas |
| `GET` | `/status/{task_id}` | Status de processamento em tempo real |
| `GET` | `/conversations` | Listagem de conversas |
| `GET` | `/` | Health check |
| `GET` | `/health` | Status detalhado do sistema |
| `GET` | `/docs` | Documentação Swagger UI |

---

## Configurando o Ambiente

### Passo 1: Criar um ambiente virtual (venv)

```bash
python -m venv venv
```

### Passo 2: Ativar o ambiente virtual

No Windows (PowerShell):

```bash
.\venv\Scripts\activate
```

No Linux/macOS:

```bash
source venv/bin/activate
```

### Passo 3: Instalar as dependências

```bash
pip install -r requirements.txt
```

### Passo 4: Configurar variáveis de ambiente

Copie `.env.example` para `.env` e preencha as variáveis necessárias (banco de dados, chaves secretas, OpenAI API key, etc.).

### Passo 5: Rodar o projeto

```bash
uvicorn main:app --reload
```

A API estará disponível em `http://localhost:8000` e a documentação em `http://localhost:8000/docs`.

> **Requisito:** Python 3.8+


## Stripe Setup (Pagamentos)

### 1. Configurar variáveis de ambiente

Use o arquivo `/.env.example` como base e preencha no seu `/.env`:

- `STRIPE_PUBLIC_KEY`
- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_START_PRICE_ID`
- `STRIPE_MEDIUM_PRICE_ID`
- `STRIPE_PRO_PRICE_ID`
- `PAYMENT_SUCCESS_URL`
- `PAYMENT_CANCEL_URL`

### 2. Criar produtos e precos no Stripe Dashboard

No Stripe Dashboard:

1. Crie os produtos/planos do sistema (basic, premium, enterprise).
2. Copie os `price_id` gerados.
3. Mapeie os IDs nas variaveis `STRIPE_*_PRICE_ID`.

### 3. Registrar webhook no Stripe

Crie um endpoint webhook apontando para:

- `https://SEU_DOMINIO/api/v1/webhooks/stripe`

Eventos minimos recomendados:

- `checkout.session.completed`
- `customer.subscription.created`
- `customer.subscription.updated`
- `customer.subscription.deleted`
- `invoice.payment_succeeded`
- `invoice.payment_failed`

Copie o signing secret para `STRIPE_WEBHOOK_SECRET`.

### 4. Endpoints de pagamento disponiveis

- `GET /api/v1/payment/config`
- `POST /api/v1/payment/checkout`
- `GET /api/v1/payment/subscription`
- `POST /api/v1/payment/update-subscription`
- `POST /api/v1/payment/cancel-subscription`
- `GET /api/v1/payment/invoices`
- `POST /api/v1/webhooks/stripe`

### 5. Teste local rapido (Stripe CLI)

1. Inicie a API local.
2. Encaminhe eventos para local:

```bash
stripe listen --forward-to localhost:8000/api/v1/webhooks/stripe
```

3. Dispare evento de teste:

```bash
stripe trigger checkout.session.completed
```

4. Valide no banco:

- insercao em `payment_events`
- atualizacao de assinatura em `users`
- upsert em `invoices` (quando aplicavel)


## Migrações de Banco (Alembic)

O projeto agora possui Alembic configurado com:

- [alembic.ini](alembic.ini)
- [alembic/env.py](alembic/env.py)
- [alembic/versions/0001_initial_schema.py](alembic/versions/0001_initial_schema.py)

No startup da API, o sistema executa automaticamente `alembic upgrade head`.

### Fluxo recomendado para novas mudanças de modelo

1. Altere seus modelos SQLAlchemy.
2. Gere uma nova migration:

	`alembic revision --autogenerate -m "descrição da mudança"`

3. Rode a API normalmente (`uvicorn main:app --reload`), e a migration será aplicada no startup.

Se preferir aplicar manualmente:

`alembic upgrade head`


