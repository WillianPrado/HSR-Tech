# HSR-Tech
Python e IA

Configurando o Ambiente Python para o Projeto HSR-Tech
Vamos configurar um ambiente virtual e instalar as dependências do projeto passo a passo.

Passo 1: Criar um ambiente virtual (venv)
Recomendo usar o venv que já vem com Python:

bash
python -m venv venv
Passo 2: Ativar o ambiente virtual
No Windows (PowerShell):

bash
.\venv\Scripts\activate
Você saberá que o ambiente está ativado quando vir (venv) no início do prompt.

Passo 3: Instalar as dependências
Vamos instalar os requisitos do arquivo requirements.txt:

bash
pip install -r requirements.txt
Passo 4: Verificar instalações críticas
Algumas dependências importantes que seu projeto parece ter (baseado nos arquivos):

FastAPI (para main.py, routes/, etc.)

SQLAlchemy (para models/, crud.py)

Python-dotenv (para .env)

Outras como PyJWT (para auth.py)

Passo 5: Configurar variáveis de ambiente
Verifique o arquivo .env.example e certifique-se que seu .env tem todas as variáveis necessárias configuradas (como conexão com banco de dados, chaves secretas, etc.).

Passo 6: Rodar o projeto
Para executar o projeto FastAPI:

bash
uvicorn main:app --reload
Dicas adicionais:
Se houver erros na instalação:

Verifique a versão do Python (recomendo 3.8+)


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


