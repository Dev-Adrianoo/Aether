"""
Processamento de comandos de voz.
Separação clara entre reconhecimento e processamento.
"""

import logging
import time
import difflib
import unicodedata
from datetime import datetime
from typing import Optional, Callable, Dict, Any, List
from pathlib import Path
import json

logger = logging.getLogger(__name__)

class CommandProcessor:
    """Processa comandos de voz extraídos do texto"""

    def __init__(self, wake_word: str = "lumina", cooldown: float = 2.0, fuzzy_threshold: float = 0.88,
                 conversation_timeout: float = 120.0):
        self.wake_word = wake_word.lower()
        self.cooldown = cooldown
        self.fuzzy_threshold = fuzzy_threshold
        self.last_wake_time = 0

        self.wake_variations = self._generate_wake_variations(wake_word)

        self.on_wake_detected: Optional[Callable] = None
        self.on_command_detected: Optional[Callable] = None

        self.command_handlers: Dict[str, Callable] = {}

        self._conv_timeout = conversation_timeout
        self._conv_last = 0.0

    def _normalize(self, text: str) -> str:
        """Remove acentos para comparação fonética"""
        return unicodedata.normalize('NFD', text).encode('ascii', 'ignore').decode()

    def _generate_wake_variations(self, word: str) -> List[str]:
        """Gera variações fonéticas comuns para português"""
        variations = [word.lower()]

        phonetic_variations = [
            word.lower(),
            "lumina",
        ]

        for var in phonetic_variations:
            if var not in variations:
                variations.append(var)

        logger.debug(f"Wake word variations: {variations}")
        return variations

    def register_command(self, command_type: str, handler: Callable):
        self.command_handlers[command_type] = handler

    @property
    def in_conversation(self) -> bool:
        return (time.time() - self._conv_last) < self._conv_timeout

    async def process_text(self, text: str) -> bool:
        """
        Processa texto reconhecido.
        Retorna True se wake word foi detectada ou conversa está ativa.
        """
        if not text:
            return False

        text_lower = text.lower()
        current_time = time.time()

        # Modo conversa ativo: qualquer fala vai direto pro handler sem wake word
        if self.in_conversation:
            wake_detected, matched_word = self._detect_wake_word(text_lower)
            if wake_detected:
                # Remove wake word do texto se presente
                command_start = text_lower.find(matched_word) + len(matched_word)
                command_text = text_lower[command_start:].strip() or text_lower
            else:
                command_text = text_lower

            self._conv_last = current_time
            logger.info(f"[conv] {command_text}")
            await self._process_command(command_text)
            return wake_detected

        # Fora do modo conversa: exige wake word
        wake_detected, matched_word = self._detect_wake_word(text_lower)

        if wake_detected:
            if current_time - self.last_wake_time < self.cooldown:
                logger.debug(f"Wake word em cooldown: {matched_word}")
                return True

            self.last_wake_time = current_time
            self._conv_last = current_time
            logger.info(f"Wake word detectada: '{matched_word}'")

            wake_pos = text_lower.find(matched_word)
            after = text_lower[wake_pos + len(matched_word):].strip()
            before = text_lower[:wake_pos].strip().rstrip(",. ")
            # "vê minha tela, lumina" → usa o que veio antes do wake word
            command_text = after or before

            if command_text:
                await self._process_command(command_text)
            else:
                logger.info("Wake word sem comando — modo conversa ativado")

            if self.on_wake_detected:
                await self.on_wake_detected()

            return True

        return False

    def _detect_wake_word(self, text: str) -> tuple[bool, str]:
        """
        Detecta wake word com fuzzy matching.
        Retorna (detectada, palavra_detectada)
        """
        # Verificar variações exatas primeiro (normalizado para ignorar acentos)
        text_norm = self._normalize(text)
        for variation in self.wake_variations:
            if self._normalize(variation) in text_norm:
                return True, variation

        # Fuzzy matching para palavras próximas (normalizado — sem acentos)
        words = text.split()
        for word in words:
            word_norm = self._normalize(word)

            similarity = difflib.SequenceMatcher(None, word_norm, self._normalize(self.wake_word)).ratio()
            if similarity >= self.fuzzy_threshold:
                logger.debug(f"Fuzzy match: '{word}' ~ '{self.wake_word}' ({similarity:.2f})")
                return True, word

            for variation in self.wake_variations:
                similarity = difflib.SequenceMatcher(None, word_norm, self._normalize(variation)).ratio()
                if similarity >= self.fuzzy_threshold:
                    logger.debug(f"Fuzzy match: '{word}' ~ '{variation}' ({similarity:.2f})")
                    return True, variation

        return False, ""

    async def _process_command(self, command_text: str):
        """Processa texto do comando"""
        logger.info(f"Processando comando: {command_text}")

        # Classificar comando
        command_type = self._classify_command(command_text)
        confidence = self._calculate_confidence(command_text)

        logger.info(f"Comando classificado como: {command_type} (confiança: {confidence:.2f})")

        # Log do comando
        await self._log_command(command_text, command_type, confidence)

        # Executar handler se registrado
        if command_type in self.command_handlers:
            logger.info(f"Executando handler para: {command_type}")
            try:
                await self.command_handlers[command_type](command_text, confidence)
            except Exception as e:
                logger.error(f"Erro no handler do comando: {e}")
        else:
            logger.warning(f"Nenhum handler registrado para: {command_type}")

        # Callback geral
        if self.on_command_detected:
            await self.on_command_detected(command_text, confidence, command_type)

    def _classify_command(self, text: str) -> str:
        """
        Classificador leve — só para stop (segurança) e terminal.
        Tudo mais vai pro LLM router em main.py.
        """
        text_lower = text.lower()

        # Stop é crítico — não pode depender de API
        if any(p in text_lower for p in ["para tudo", "pare tudo", "encerra tudo", "sai agora", "fechar tudo", "lumina para", "lumina encerra"]):
            return "stop"

        # Tudo mais: LLM decide
        return "llm_route"

    def _calculate_confidence(self, text: str) -> float:
        """Calcula confiança no reconhecimento"""
        if len(text.split()) < 2:
            return 0.5

        confidence_keywords = ["tela", "print", "captura", "mostra", "olha", "foto"]
        text_lower = text.lower()

        confidence = 0.5
        for keyword in confidence_keywords:
            if keyword in text_lower:
                confidence += 0.1

        return min(confidence, 0.95)

    async def _log_command(self, text: str, command_type: str, confidence: float):
        """Registra comando no log"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "command": text,
            "type": command_type,
            "confidence": confidence,
            "wake_word": self.wake_word
        }

        try:
            log_dir = Path("data/command_logs")
            log_dir.mkdir(parents=True, exist_ok=True)

            log_file = log_dir / "commands.jsonl"
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

            logger.debug(f"Comando registrado: {command_type} ({confidence:.2f})")

        except Exception as e:
            logger.error(f"Erro ao registrar comando: {e}")
