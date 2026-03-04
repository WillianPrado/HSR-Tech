import os
import re
from typing import Optional

from core.abstractions.illm_client import ILLMClient


GENERIC_TITLES = {
    "",
    "nova conversa",
    "sem título",
    "sem titulo",
    "new chat",
    "untitled",
}

SECTION_LABELS = {
    "resumo_executivo",
    "score_comercial",
    "evidencias",
    "oportunidades_riscos",
    "tecnicas_nao_usadas",
    "plano_recuperacao",
    "mensagens_prontas",
    "checklist_final",
    "conclusao_motivacional",
    "analise_disc_cliente",
}

STOPWORDS = {
    "a", "o", "as", "os", "de", "da", "do", "das", "dos", "e", "ou", "em", "no", "na", "nos", "nas",
    "para", "por", "com", "sem", "um", "uma", "uns", "umas", "que", "se", "ao", "aos", "à", "às",
}

FILE_EXTENSIONS_FOR_TITLE_REPLACE = {
    "zip",
    "txt",
    "text",
    "md",
    "csv",
    "log",
    "opus",
    "mp3",
    "wav",
    "ogg",
    "m4a",
    "aac",
    "flac",
}


def _looks_like_filename_title(title: str) -> bool:
    normalized = title.strip().lower()
    if not normalized:
        return False

    if re.search(r"\.([a-z0-9]{2,6})$", normalized):
        extension = normalized.rsplit(".", 1)[-1]
        if extension in FILE_EXTENSIONS_FOR_TITLE_REPLACE:
            return True

    tokens = normalized.replace("_", " ").split()
    for token in tokens:
        match = re.search(r"\.([a-z0-9]{2,6})$", token)
        if match and match.group(1) in FILE_EXTENSIONS_FOR_TITLE_REPLACE:
            return True

    return False


def should_update_conversation_title(current_title: Optional[str]) -> bool:
    if current_title is None:
        return True
    normalized = current_title.strip().lower()
    return normalized in GENERIC_TITLES or _looks_like_filename_title(normalized)


def _normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _normalize_label(text: str) -> str:
    value = text.strip().lower()
    value = re.sub(r"[*#`]+", "", value)
    value = value.replace(" ", "_")
    value = re.sub(r"[^a-z0-9_à-ÿ-]", "", value)
    return value


def _clean_title_candidate(text: str, max_chars: int = 60) -> str:
    value = text.strip()
    value = re.sub(r"^[#\-*\s]+", "", value)
    value = re.sub(r"[*`\[\]()]+", "", value)
    value = value.replace("_", " ")
    value = _normalize_spaces(value)
    return value[:max_chars].strip(" -_,.;:")


def _is_section_label(text: str) -> bool:
    normalized = _normalize_label(text)
    return normalized in SECTION_LABELS


def generate_title_heuristic(text: str, max_words: int = 7, max_chars: int = 60) -> str:
    cleaned = re.sub(r"[\r\n\t]+", " ", text)
    cleaned = re.sub(r"[\"'`´]+", "", cleaned)
    cleaned = _normalize_spaces(cleaned)
    if not cleaned:
        return "Nova conversa"

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("#"):
            heading = _clean_title_candidate(line, max_chars=max_chars)
            if heading and not _is_section_label(heading):
                return heading

        candidate = _clean_title_candidate(line, max_chars=max_chars)
        if candidate and not _is_section_label(candidate):
            if re.match(r"^\*\*[^*]+\*\*$", line):
                continue
            break
    else:
        candidate = ""

    if candidate:
        tokens = re.findall(r"[\wÀ-ÿ-]+", candidate, flags=re.UNICODE)
    else:
        first_sentence = re.split(r"[.!?;:]", cleaned)[0].strip()
        tokens = re.findall(r"[\wÀ-ÿ-]+", first_sentence, flags=re.UNICODE)

    content_tokens = [token for token in tokens if token.lower() not in STOPWORDS]
    selected = content_tokens[:max_words] if len(content_tokens) >= 3 else tokens[:max_words]

    title = " ".join(selected).strip()
    title = title[:max_chars].strip(" -_,.;:")
    return title or "Nova conversa"


async def suggest_conversation_title(
    text: str,
    llm_client: Optional[ILLMClient] = None,
) -> str:
    mode = os.getenv("TITLE_GENERATION_MODE", "hybrid").strip().lower()

    heuristic_title = generate_title_heuristic(text)
    if mode == "heuristic" or llm_client is None:
        return heuristic_title

    if mode not in {"hybrid", "llm"}:
        return heuristic_title

    title_prompt = (
        "Gere um título curto para esta conversa de vendas. "
        "Regras: português do Brasil, máximo 6 palavras, sem aspas, sem pontuação final, sem markdown. "
        f"Texto: {text}"
    )
    title_model = os.getenv("TITLE_MODEL", "deepseek-chat")

    try:
        llm_title = await llm_client.send_message(title_prompt, model=title_model)
        if not llm_title:
            return heuristic_title
        llm_title = _normalize_spaces(llm_title).strip("\"'`´ ")
        llm_title = llm_title.split("\n")[0][:60].strip(" -_,.;:")
        if not llm_title or _is_section_label(llm_title):
            return heuristic_title
        return llm_title
    except Exception:
        return heuristic_title
