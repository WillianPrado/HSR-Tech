import logging
from pathlib import Path
from typing import List, Set

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def clean_extracted_files(
    base_dir: Path,
    keep_extensions: Set[str] = {'.txt', '.text'},
    delete_zips: bool = True,
    exclude_dirs: Set[str] = {'backups', 'important'}
) -> List[str]:
    """
    Remove arquivos desnecessários no diretório base e subdiretórios,
    mantendo apenas os com extensões permitidas e preservando todas as pastas.
    
    Args:
        base_dir (Path): Caminho para o diretório raiz onde será feita a limpeza.
        keep_extensions (Set[str]): Extensões de arquivos a manter (com ponto).
        delete_zips (bool): Se True, remove arquivos .zip mesmo se estiverem na lista de extensões a manter.
        exclude_dirs (Set[str]): Nomes de diretórios a serem ignorados durante a varredura.
    
    Returns:
        List[str]: Caminhos dos arquivos que foram removidos.
    """
    deleted_files = []

    if not base_dir.is_dir():
        logger.error(f"O caminho informado não é um diretório válido: {base_dir}")
        return deleted_files

    try:
        for file_path in base_dir.rglob("*"):
            if not file_path.is_file():
                continue

            # Verifica se o arquivo está dentro de uma pasta excluída
            if any(excluded in file_path.parts for excluded in exclude_dirs):
                continue

            # Define se o arquivo deve ser mantido
            ext = file_path.suffix.lower()
            if (ext in keep_extensions) and not (delete_zips and ext == '.zip'):
                continue

            try:
                file_path.unlink()
                deleted_files.append(str(file_path))
            except Exception as e:
                logger.warning(f"Erro ao excluir {file_path}: {e}")

        logger.info(f"{len(deleted_files)} arquivos removidos com sucesso.")
        return deleted_files

    except Exception as e:
        logger.error(f"Erro geral durante a limpeza: {e}")
        raise
