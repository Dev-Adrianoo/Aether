"""
Dicionário de correção do STT.
Quando o usuário corrige uma transcrição errada, salva o mapeamento
e aplica automaticamente nas próximas transcrições.

Formato do arquivo: data/stt_corrections.json
{"fashion kellyn": "function calling", "éder": "lumina", ...}
"""

import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

CORRECTIONS_FILE = Path("data/stt_corrections.json")


class STTCorrector:

    def __init__(self):
        self._corrections: dict[str, str] = {}
        self._load()

    def _load(self):
        if CORRECTIONS_FILE.exists():
            try:
                self._corrections = json.loads(CORRECTIONS_FILE.read_text(encoding="utf-8"))
                logger.info(f"STT corrections carregadas: {len(self._corrections)} entradas")
            except Exception as e:
                logger.warning(f"Erro ao carregar corrections: {e}")
                self._corrections = {}

    def apply(self, text: str) -> str:
        """Aplica correções conhecidas ao texto reconhecido pelo STT."""
        result = self._apply_builtin_patterns(text)
        for wrong, right in self._corrections.items():
            if wrong.lower() in result.lower():
                result = result.lower().replace(wrong.lower(), right)
                logger.debug(f"STT corrigido: '{wrong}' -> '{right}'")
        return result

    def _apply_builtin_patterns(self, text: str) -> str:
        """Corrige padroes comuns do STT em portugues falado brasileiro."""
        result = text.strip()
        lowered = result.lower()

        asks_lumina_to_answer = any(
            phrase in lowered
            for phrase in [
                "me fala", "me falar", "me diga", "diz o que",
                "o que tem", "o que aparece", "o que voce ve", "o que você vê",
            ]
        )
        if asks_lumina_to_answer:
            result = re.sub(
                r"\b(eu\s+)?vou\s+tirar\s+(um\s+)?print\b",
                "tira print",
                result,
                flags=re.IGNORECASE,
            )

        replacements = [
            (r"\bme\s+falar\b", "me fala"),
            (r"\bd[aá]\s+uma\s+olhada\b", "olha"),
            (r"\bd[aá]\s+um\s+olhada\b", "olha"),
            (r"\btela\s+da\s+direita\b", "tela direita"),
            (r"\btela\s+do\s+lado\s+direito\b", "tela direita"),
            (r"\bmonitor\s+da\s+direita\b", "monitor direito"),
            (r"\bprint\s+screen\b", "print"),
            (r"\bscreenshot\b", "print"),
        ]
        for pattern, replacement in replacements:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

        return " ".join(result.split())

    # Palavras comuns que nunca devem virar correção — são verbos de ação, não erros de STT
    _BLOCKED = {"abrir", "fechar", "criar", "fazer", "ir", "ver", "usar", "colocar",
                "pedir", "falar", "dizer", "abre", "fecha", "cria", "faz"}

    def add(self, wrong: str, right: str):
        """Adiciona ou atualiza uma correção e persiste no arquivo."""
        wrong_clean = wrong.lower().strip()
        right_clean = right.strip()
        if len(wrong_clean) < 5:
            logger.warning(f"Correcao STT rejeitada (muito curta): '{wrong_clean}'")
            return
        if wrong_clean in self._BLOCKED or right_clean.lower() in self._BLOCKED:
            logger.warning(f"Correcao STT rejeitada (palavra bloqueada): '{wrong_clean}' -> '{right_clean}'")
            return
        if wrong_clean and right_clean and wrong_clean != right_clean:
            self._corrections[wrong_clean] = right_clean
            self._save()
            logger.info(f"Correcao salva: '{wrong_clean}' -> '{right_clean}'")

    def _save(self):
        CORRECTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        CORRECTIONS_FILE.write_text(
            json.dumps(self._corrections, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
