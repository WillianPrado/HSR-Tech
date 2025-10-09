from abc import ABC, abstractmethod
import asyncio
from typing import Optional
from anyio import Path
import logging
from services.reports.deepseek_client import enviar_mensagem_para_deepseek
from services.reports.pdf_utils import salvar_texto_em_pdf_simples, salvar_markdown_em_pdf_visual
import datetime
from core.status_tracker import set_status

logger = logging.getLogger(__name__)
# Interface para tracking de status
class StatusTracker(ABC):
    @abstractmethod
    async def update(self, zip_id: str, message: str, progress: float):
        pass

class DatabaseStatusTracker(StatusTracker):
    async def update(self, zip_id: str, message: str, progress: float):
        await set_status(zip_id, message, progress)

def carregar_arquivo(caminho):
    try:
        with open(caminho, 'r', encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        print(f"❌ Erro ao ler '{caminho}': {e}")
        return None

def combinar_prompt_conversa(prompt, conversa):
    return f"{prompt}\n\nTRANSCRIÇÃO DA CONVERSA:\n{conversa}"

async def processar_conversa_para_pdf(
    prompt_path: Path,
    chat_path: Path,
    output_pdf: Path,
    tracker: Optional[StatusTracker] = None,
    zip_id: Optional[str] = None
):
    """
    Processa uma conversa e gera um PDF de análise.

    Args:
        prompt_path: Caminho para o arquivo de prompt
        chat_path: Caminho para o arquivo de chat
        output_pdf: Caminho de saída para o PDF
        tracker: Instância do StatusTracker para atualizações
        zip_id: ID do processo para tracking
    """

    async def update_status(message: str, progress: float):
        """Atualiza o status se tracker e zip_id estiverem disponíveis"""
        if tracker and zip_id:
            await tracker.update(zip_id, message, progress)

    def validar_arquivo(path: Path, descricao: str):
        """Função auxiliar para validação de arquivos"""
        if not path.exists():
            error_msg = f"{descricao} não encontrado: {path}"
            return error_msg
        return None
    try:
        # Validação dos arquivos
        prompt_error = validar_arquivo(prompt_path, "Arquivo de prompt")
        if prompt_error:
            await update_status(prompt_error, 0)
            raise FileNotFoundError(prompt_error)

        chat_error = validar_arquivo(chat_path, "Arquivo de chat")
        if chat_error:
            await update_status(chat_error, 0)
            raise FileNotFoundError(chat_error)

        # Carrega os conteúdos dos arquivos
        prompt = carregar_arquivo(prompt_path)
        conversa = carregar_arquivo(chat_path)

        # Verifica se o conteúdo dos arquivos está correto
        if not prompt or not conversa:
            error_msg = "Prompt ou conversa inválidos"
            await update_status(error_msg, 0)
            raise ValueError(error_msg)

        # Prepara o início do processamento
        await update_status("Preparando análise...", 0.62)
        mensagem_completa = combinar_prompt_conversa(prompt, conversa)

        # Realiza a análise via IA
        await update_status("IA analisando negociação ... (pode demorar 5 minutos)", 0.66)
        resposta = enviar_mensagem_para_deepseek(mensagem_completa)

        if not resposta:
            error_msg = "Resposta da IA vazia"
            await update_status(error_msg, 0)
            raise RuntimeError(error_msg)

        # Preparação do diretório de saída para o PDF
        output_pdf.parent.mkdir(parents=True, exist_ok=True)

        # Geração do relatório
        await update_status("Gerando relatório...", 0.7)
        await asyncio.to_thread(salvar_markdown_em_pdf_visual, resposta, output_pdf)

        # Log de sucesso
        logger.info(f"Relatório gerado: {output_pdf}")

    except FileNotFoundError as e:
        error_msg = f"Erro de arquivo: {str(e)}"
        await update_status(error_msg, 0)
        logger.error(error_msg)
        raise  # Levanta a exceção para ser tratada mais acima, caso necessário

    except ValueError as e:
        error_msg = f"Erro de valor: {str(e)}"
        await update_status(error_msg, 0)
        logger.error(error_msg)
        raise  # Levanta a exceção para ser tratada mais acima, caso necessário

    except RuntimeError as e:
        error_msg = f"Erro de execução: {str(e)}"
        await update_status(error_msg, 0)
        logger.error(error_msg)
        raise  # Levanta a exceção para ser tratada mais acima, caso necessário

    except Exception as e:
        error_msg = f"Falha no processamento: {str(e)}"
        await update_status(error_msg, 0)
        logger.error(error_msg)
        raise  # Levanta a exceção para ser tratada mais acima, caso necessário
