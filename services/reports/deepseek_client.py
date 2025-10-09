import requests
import os

API_KEY = os.getenv("DEEP_SEEK_API_KEY")  # Substitua pela sua chave
API_URL = 'https://api.deepseek.com/chat/completions'
def enviar_mensagem_para_deepseek(mensagem):
    headers = {
        'Authorization': f'Bearer {API_KEY}',
        'Content-Type': 'application/json'
    }

    body = {
        "model": "deepseek-reasoner",
        "messages": [
            {"role": "user", "content": mensagem}
        ]
    }

    resposta = requests.post(API_URL, headers=headers, json=body)
    if resposta.status_code == 200:
        dados = resposta.json()
        return dados['choices'][0]['message']['content']
    else:
        print(f"❌ Erro: {resposta.status_code} - {resposta.text}")
        return None
