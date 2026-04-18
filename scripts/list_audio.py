#!/usr/bin/env python3
"""
Script utilitário para listar dispositivos de áudio de entrada.
Dentro da arquitetura do projeto — usa AudioCaptureFactory.
"""

import sys
from pathlib import Path

# Adicionar diretório pai ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

def main():
    try:
        from src.voice.audio_capture import AudioCaptureFactory

        print("=== DISPOSITIVOS DE ÁUDIO DE ENTRADA (MICROFONES) ===")
        devices = AudioCaptureFactory.list_audio_devices()

        if isinstance(devices, dict) and "error" in devices:
            print(f"Erro: {devices['error']}")
            return 1

        print(f"\nTotal de dispositivos de entrada encontrados: {len(devices)}")
        print("-" * 80)

        possible_quest = []
        usb_audio_devices = []

        for idx, info in devices.items():
            if not isinstance(info, dict):
                continue

            name = info.get("name", "Desconhecido")
            channels = info.get("input_channels", 0)
            samplerate = info.get("default_samplerate", "N/A")

            print(f"Índice: {idx}")
            print(f"  Nome: {name}")
            print(f"  Canais entrada: {channels}")
            print(f"  Taxa amostragem: {samplerate}")

            # Verificar se parece ser Meta Quest
            name_lower = name.lower()
            if "quest" in name_lower or "meta" in name_lower or "vr" in name_lower or "oculus" in name_lower:
                print(f"  ⚠️  POSSÍVEL META QUEST DETECTADO!")
                possible_quest.append((idx, name))
            elif "usb audio" in name_lower:
                usb_audio_devices.append((idx, name))

            if "hostapi" in info:
                print(f"  Host API: {info['hostapi']}")

            print()

        # Análise dos dispositivos
        if possible_quest:
            print(f"\n⚠️  Dispositivos Meta Quest/Oculus encontrados:")
            for idx, name in possible_quest:
                print(f"  - Índice {idx}: {name}")
            print(f"\n  Para usar o microfone do headset, adicione ao .env:")
            print(f"    AUDIO_DEVICE_INDEX={possible_quest[0][0]}")

        if usb_audio_devices:
            print(f"\n🔌 Dispositivos USB Audio (microfone de mesa):")
            for idx, name in usb_audio_devices:
                print(f"  - Índice {idx}: {name}")
            if not possible_quest:
                print(f"\n  Para usar um dispositivo USB, adicione ao .env:")
                print(f"    AUDIO_DEVICE_INDEX={usb_audio_devices[0][0]}")

        print("\n=== COMO CONFIGURAR NO LUMINA ===")
        print("1. Edite o arquivo .env ou .env.local")
        print("2. Adicione ou altere a linha:")
        print("   AUDIO_DEVICE_INDEX=<índice_do_dispositivo>")
        print("3. Reinicie o Lumina: python main.py")
        print("\nExemplo para Meta Quest: AUDIO_DEVICE_INDEX=34")
        print("Exemplo para microfone USB: AUDIO_DEVICE_INDEX=2")
        print("\nPara usar o dispositivo padrão do sistema, deixe a linha comentada ou removida.")
        print("\nDica: Teste rapidamente com:")
        print("  AUDIO_DEVICE_INDEX=34 python main.py")

        return 0

    except ImportError as e:
        print(f"Erro de importação: {e}")
        print("\nInstale as dependências:")
        print("  pip install sounddevice")
        print("  Ou: pip install pyaudio")
        return 1
    except Exception as e:
        print(f"Erro inesperado: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())