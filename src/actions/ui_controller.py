"""
UIController — localiza texto na tela via OCR e clica via PyAutoGUI.
Dependências: pyautogui, pytesseract, Pillow, mss
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ClickResult:
    success: bool
    x: int = 0
    y: int = 0
    message: str = ""


async def find_and_click(target_text: str, monitor_index: int = 0) -> ClickResult:
    """
    Captura a tela, localiza target_text via OCR e clica no centro do elemento.
    monitor_index=0 captura todos os monitores combinados.
    """
    try:
        import mss
        from PIL import Image
        import pytesseract
        import pyautogui
    except ImportError as e:
        return ClickResult(False, message=f"Dependência ausente: {e}")

    try:
        img, offset_x, offset_y = await asyncio.to_thread(_capture, monitor_index)
    except Exception as e:
        return ClickResult(False, message=f"Erro ao capturar tela: {e}")

    try:
        pos = await asyncio.to_thread(_locate_text, img, target_text)
    except Exception as e:
        return ClickResult(False, message=f"Erro no OCR: {e}")

    if pos is None:
        return ClickResult(False, message=f"Texto '{target_text}' não encontrado na tela")

    rel_x, rel_y = pos
    abs_x = offset_x + rel_x
    abs_y = offset_y + rel_y

    try:
        await asyncio.to_thread(pyautogui.click, abs_x, abs_y)
        logger.info(f"Clicou em '{target_text}' em ({abs_x}, {abs_y})")
        return ClickResult(True, x=abs_x, y=abs_y, message=f"Clicado em '{target_text}'")
    except Exception as e:
        return ClickResult(False, message=f"Erro ao clicar: {e}")


def _capture(monitor_index: int) -> Tuple:
    import mss
    from PIL import Image

    with mss.mss() as sct:
        n = len(sct.monitors) - 1
        if monitor_index == 0:
            mon = sct.monitors[0]
        else:
            mon = sct.monitors[max(1, min(monitor_index, n))]
        shot = sct.grab(mon)
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        return img, mon["left"], mon["top"]


def _locate_text(img, target: str) -> Optional[Tuple[int, int]]:
    import pytesseract
    from config import config
    pytesseract.pytesseract.tesseract_cmd = config.vision.tesseract_cmd

    target_lower = target.lower().strip()
    data = pytesseract.image_to_data(img, lang="por+eng", output_type=pytesseract.Output.DICT)

    # Build word-by-word list with positions
    words = data["text"]
    n = len(words)

    # Try multi-word match first (sliding window)
    target_words = target_lower.split()
    wlen = len(target_words)

    for i in range(n - wlen + 1):
        chunk = [words[j].lower().strip() for j in range(i, i + wlen)]
        if chunk == target_words and all(int(data["conf"][i + k]) > 30 for k in range(wlen)):
            xs = [data["left"][i + k] for k in range(wlen)]
            ys = [data["top"][i + k] for k in range(wlen)]
            ws = [data["width"][i + k] for k in range(wlen)]
            hs = [data["height"][i + k] for k in range(wlen)]
            cx = (min(xs) + max(x + w for x, w in zip(xs, ws))) // 2
            cy = (min(ys) + max(y + h for y, h in zip(ys, hs))) // 2
            return cx, cy

    # Fallback: partial match on single best word
    best_conf = -1
    best_pos = None
    for i in range(n):
        word = words[i].lower().strip()
        conf = int(data["conf"][i])
        if conf > 30 and target_lower in word:
            if conf > best_conf:
                best_conf = conf
                cx = data["left"][i] + data["width"][i] // 2
                cy = data["top"][i] + data["height"][i] // 2
                best_pos = (cx, cy)

    return best_pos
