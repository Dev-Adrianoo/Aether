#!/usr/bin/env python3
"""
Teste simples de microfone.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

async def test_simple():
    """Teste simples de captura"""
    print("🎤 Teste SIMPLES de microfone")

    try:
        import sounddevice as sd
        import numpy as np

        print(f"Dispositivos de áudio disponíveis:")
        print(sd.query_devices())

        # Testar captura de 2 segundos
        print("\n🎤 Gravando 2 segundos... FALE ALGO!")

        sample_rate = 16000
        duration = 2

        audio_data = sd.rec(
            int(duration * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype=np.int16
        )
        sd.wait()

        print(f"✅ Áudio capturado: {audio_data.shape}")
        print(f"   Forma: {audio_data.shape}")
        print(f"   Tipo: {audio_data.dtype}")
        print(f"   Média: {np.mean(np.abs(audio_data)):.2f}")

        if np.mean(np.abs(audio_data)) < 10:
            print("⚠️  Áudio muito silencioso - verifique microfone")
        else:
            print("✅ Áudio com volume OK")

        # Salvar para teste
        import wave
        with wave.open('test_mic.wav', 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_data.tobytes())

        print("✅ Arquivo salvo: test_mic.wav")

    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_simple())