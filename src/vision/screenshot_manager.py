"""
Gerenciador de Screenshots Inteligente
Captura telas baseado em triggers e intervalos, com economia de contexto
"""

import asyncio
import time
from datetime import datetime
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class ScreenshotManager:
    """Gerencia captura inteligente de screenshots"""

    def __init__(self, config_path=None):
        self.trigger_words = ["tela", "print", "screenshot", "foto", "mostra", "olha", "captura"]
        self.last_screenshot_time = 0
        self.screenshot_interval = 60  # segundos (configurável)
        self.min_interval_for_context = 300  # 5 minutos entre envios para contexto

        self.last_context_send_time = 0
        self.monitoring_active = False

        # Callbacks
        self.on_important_screenshot = None

        logger.info("ScreenshotManager inicializado")

    async def capture_and_analyze(self, reason="interval", monitor_index: int = 1):
        """Captura e analisa screenshot"""
        try:
            screenshot = await self._capture_screen(monitor_index=monitor_index)
            analysis = await self._analyze_screenshot(screenshot)

            # Decidir se envia para contexto
            should_send = await self._should_send_to_context(analysis, reason)

            if should_send:
                logger.info(f"Enviando screenshot para contexto (razão: {reason})")
                if self.on_important_screenshot:
                    await self.on_important_screenshot(screenshot, analysis)

            # Salvar localmente para histórico
            await self._save_screenshot(screenshot, analysis, reason)

            self.last_screenshot_time = time.time()
            analysis['filepath'] = screenshot.get('filepath', '')
            analysis['dimensions'] = screenshot.get('dimensions', (0, 0))
            return analysis

        except Exception as e:
            logger.error(f"Erro ao capturar/analisar screenshot: {e}")
            return {"error": str(e), "has_errors": True}

    async def _capture_screen(self, monitor_index: int = 1):
        """Captura screenshot da tela usando mss (implementação real)"""
        try:
            import mss
            import mss.tools

            with mss.mss() as sct:
                n_monitors = len(sct.monitors) - 1  # monitors[0] é o combinado
                idx = max(1, min(monitor_index, n_monitors))
                monitor = sct.monitors[idx]

                # Capturar screenshot
                screenshot = sct.grab(monitor)

                # Converter para formato útil
                from PIL import Image
                img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

                # Salvar temporariamente para análise (opcional)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                save_path = Path("data/screenshots") / f"screenshot_{timestamp}.png"
                save_path.parent.mkdir(parents=True, exist_ok=True)
                img.save(save_path, "PNG")

                logger.debug(f"Screenshot capturado: {screenshot.width}x{screenshot.height}")

                return {
                    "timestamp": datetime.now().isoformat(),
                    "data": screenshot,
                    "pil_image": img,
                    "dimensions": (screenshot.width, screenshot.height),
                    "filepath": str(save_path),
                    "monitor": monitor
                }

        except ImportError as e:
            logger.error(f"mss não instalado: {e}")
            return {
                "timestamp": datetime.now().isoformat(),
                "data": None,
                "error": "mss não instalado",
                "dimensions": (0, 0)
            }
        except Exception as e:
            logger.error(f"Erro ao capturar screenshot: {e}")
            return {
                "timestamp": datetime.now().isoformat(),
                "data": None,
                "error": str(e),
                "dimensions": (0, 0)
            }

    async def _analyze_screenshot(self, screenshot):
        """Analisa o screenshot para contexto"""
        # TODO: Implementar análise com OpenCV
        analysis = {
            "timestamp": screenshot["timestamp"],
            "summary": "Tela capturada",
            "has_errors": False,
            "needs_attention": False,
            "detected_elements": ["unknown"],
            "change_significance": "low"
        }

        # Simulação de análise
        current_time = time.time()
        if current_time - self.last_context_send_time > self.min_interval_for_context:
            analysis["change_significance"] = "medium"

        return analysis

    async def _should_send_to_context(self, analysis, reason):
        """Decide se deve enviar screenshot para contexto do OpenClaude"""
        current_time = time.time()

        # Regras de envio:
        # 1. Se foi trigger por voz -> SEMPRE envia
        if reason == "voice_trigger":
            self.last_context_send_time = current_time
            return True

        # 2. Se tem erros detectados -> SEMPRE envia
        if analysis.get("has_errors", False):
            self.last_context_send_time = current_time
            return True

        # 3. Se precisa de atenção -> SEMPRE envia
        if analysis.get("needs_attention", False):
            self.last_context_send_time = current_time
            return True

        # 4. Se passou muito tempo desde último envio -> envia
        if current_time - self.last_context_send_time > self.min_interval_for_context:
            self.last_context_send_time = current_time
            return True

        # 5. Mudança significativa -> avalia
        if analysis.get("change_significance") in ["high", "medium"]:
            # Só envia se não enviou recentemente
            if current_time - self.last_context_send_time > 60:  # 1 minuto
                self.last_context_send_time = current_time
                return True

        return False

    async def _save_screenshot(self, screenshot, analysis, reason):
        """Salva screenshot localmente para histórico"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}_{reason}.json"

            save_dir = Path("data/screenshots")
            save_dir.mkdir(parents=True, exist_ok=True)

            save_data = {
                "screenshot": screenshot,
                "analysis": analysis,
                "reason": reason,
                "saved_at": datetime.now().isoformat()
            }

            # TODO: Salvar como JSON ou imagem
            logger.debug(f"Screenshot salvo: {filename}")

        except Exception as e:
            logger.error(f"Erro ao salvar screenshot: {e}")

    async def check_trigger_words(self, text):
        """Verifica se texto contém palavras trigger"""
        if not text:
            return False

        text_lower = text.lower()
        for word in self.trigger_words:
            if word in text_lower:
                return True
        return False

    def should_capture_screenshot(self, transcribed_text=None):
        """Decide se deve capturar screenshot baseado em triggers ou intervalo"""
        current_time = time.time()

        # Trigger por palavra-chave no texto transcrito
        if transcribed_text:
            text_lower = transcribed_text.lower()
            if any(word in text_lower for word in self.trigger_words):
                return True, "trigger_word"

        # Trigger por intervalo de tempo
        if current_time - self.last_screenshot_time >= self.screenshot_interval:
            return True, "interval"

        return False, None

    async def start_monitoring(self):
        """Inicia monitoramento por intervalo"""
        self.monitoring_active = True
        logger.info("Monitoramento de screenshots iniciado")

        while self.monitoring_active:
            try:
                current_time = time.time()

                # Verificar se é hora de capturar por intervalo
                if current_time - self.last_screenshot_time >= self.screenshot_interval:
                    await self.capture_and_analyze(reason="interval")

                # Aguardar antes de verificar novamente
                await asyncio.sleep(5)  # Verificar a cada 5 segundos

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Erro no loop de monitoramento: {e}")
                await asyncio.sleep(10)

    async def shutdown(self):
        """Encerra o monitoramento"""
        self.monitoring_active = False
        logger.info("ScreenshotManager encerrado")