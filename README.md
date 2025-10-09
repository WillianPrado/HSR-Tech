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


