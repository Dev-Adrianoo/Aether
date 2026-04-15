#!/usr/bin/env python3
"""
Teste de microfone com dispositivo específico.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

async def test_with_device(device_id: int):
    """Teste com dispositivo específico"""
    print(f"🎤 Testando dispositivo {device_id}")

    try:
        import sounddevice as sd
        import numpy as np

        # Verificar dispositivo
        device_info = sd.query_devices(device_id)
        print(f"Dispositivo: {device_info['name']}")
        print(f"  Canais entrada: {device_info['max_input_channels']}")
        print(f"  Taxa amostragem: {device_info['default_samplerate']}")

        # Testar captura
        sample_rate = 16000
        duration = 2

        print(f"\n🎤 Gravando 2 segundos no dispositivo {device_id}... FALE ALTO!")

        audio_data = sd.rec(
            int(duration * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype=np.int16,
            device=device_id
        )
        sd.wait()

        print(f"✅ Áudio capturado")
        print(f"   Forma: {audio_data.shape}")
        print(f"   Média absoluta: {np.mean(np.abs(audio_data)):.2f}")
        print(f"   Máximo: {np.max(np.abs(audio_data))}")

        # Salvar
        import wave
        filename = f'test_device_{device_id}.wav'
        with wave.open(filename, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_data.tobytes())

        print(f"✅ Arquivo salvo: {filename}")

        return np.mean(np.abs(audio_data))

    except Exception as e:
        print(f"❌ Erro no dispositivo {device_id}: {e}")
        return 0

async def main():
    """Testa vários dispositivos"""
    print("🔍 Testando dispositivos de entrada...")

    import sounddevice as sd

    # Dispositivos de entrada
    input_devices = []
    for i, dev in enumerate(sd.query_devices()):
        if dev['max_input_channels'] > 0:
            input_devices.append((i, dev))

    print(f"\nEncontrados {len(input_devices)} dispositivos de entrada:")

    results = []
    for i, dev in input_devices[:5]:  # Testar apenas primeiros 5
        print(f"\n--- Dispositivo {i}: {dev['name']} ---")
        volume = await test_with_device(i)
        results.append((i, dev['name'], volume))

    # Resultados
    print("\n" + "="*50)
    print("RESULTADOS (maior volume é melhor):")
    print("="*50)

    for i, name, volume in sorted(results, key=lambda x: x[2], reverse=True):
        status = "✅ BOM" if volume > 100 else "⚠️  BAIXO" if volume > 10 else "❌ SILENCIOSO"
        print(f"{i:2d}: {name[:40]:40} {volume:8.2f} {status}")

    print("\n💡 Recomendação: Use o dispositivo com maior volume")
    print("   Configure no código ou selecione manualmente")

if __name__ == "__main__":
    asyncio.run(main())