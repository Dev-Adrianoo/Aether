# Plano: Conversa Natural (Bate-Volta)

## Por que fazer

Hoje a Lumina funciona como um walkie-talkie:

```
[usuário fala] → [silêncio detectado] → [transcreve] → [classifica] → [Lumina fala] → [mute 1.5s] → [usuário fala]
```

Cada etapa é bloqueante. O resultado é uma conversa "pré-programada" — você sente que está
interagindo com um sistema, não com uma pessoa. Em humanos o padrão é diferente:

```
pessoa A fala → pessoa B já começa a processar enquanto ouve → quando A para, B responde quase imediatamente
pessoa A pode interromper B a qualquer momento
```

O objetivo é chegar nesse modelo: resposta em menos de 1 segundo depois que o usuário parar
de falar, e possibilidade de interromper a Lumina a qualquer momento.

---

## O que precisa mudar

### Problema 1 — VAD lento (silêncio fixo)

**Hoje:** `voice_listener` captura áudio em chunks e espera um timeout de silêncio
(~2s por padrão) para considerar que o usuário terminou de falar. Isso atrasa tudo.

**Solução:** Substituir o timeout de silêncio por um modelo de VAD real.
- **Silero VAD** (`silero-vad`) — modelo PyTorch leve (~1MB), detecta fim de fala em ~100ms
- Roda em CPU sem problema
- Já tem integração com `faster-whisper` via `vad_filter=True`

### Problema 2 — Mute pós-TTS bloqueia o usuário

**Hoje:** Depois que a Lumina fala, o microfone fica mudo por `post_tts_mute_seconds`
(atualmente 1.5s). Se o usuário começa a falar antes disso, a frase é cortada.

**Solução:** Remover o mute fixo e usar detecção de sobreposição:
- Enquanto o TTS toca, o VAD continua rodando em paralelo
- Se detectar energia de voz humana (frequência humana vs. frequência do speaker), para o TTS
- Isso é **barge-in**: o usuário pode interromper a Lumina no meio da frase

### Problema 3 — Pipeline sequencial (cada etapa espera a anterior)

**Hoje:** captura completa → transcrição completa → classificação → resposta

**Solução:** Pipeline em streaming:
1. **STT streaming** — `faster-whisper` suporta transcrição incremental. Enquanto o usuário
   ainda fala, os primeiros segmentos já são transcritos.
2. **Classificação antecipada** — quando o texto parcial já é suficiente para classificar
   (ex: "tira print da tela"), não espera o usuário terminar.
3. **TTS streaming** — `edge-tts` gera áudio em chunks. Começa a tocar o primeiro chunk
   enquanto ainda gera o resto.

### Problema 4 — Wake word obrigatória quebra o fluxo

**Hoje:** precisa dizer "Lumina" antes de cada frase em modo normal.

**Solução:** Modo conversa contínuo melhorado:
- Depois que o usuário fala com a Lumina, entra em modo conversa por N segundos
- Nesse modo, qualquer fala vai direto pro processamento sem wake word
- Wake word só volta a ser exigida depois de X segundos de silêncio

---

## Arquitetura alvo

```
[Microfone contínuo]
        │
        ▼
[Silero VAD] ──── detecta início de fala ────► [Buffer de áudio]
        │                                              │
        │ detecta fim de fala (~100ms)                 │
        ▼                                              ▼
[faster-whisper streaming] ◄──────────────── [chunks de áudio]
        │
        │ texto parcial disponível
        ▼
[FastCommandRouter] ──► screenshot/terminal (sem LLM)
        │
        │ texto completo
        ▼
[IntentRouter + LLM]
        │
        ▼
[edge-tts streaming] ──► [Speaker] ◄── barge-in detectado ──► [para TTS]
        │
        │ enquanto fala
        ▼
[VAD monitorando microfone] ── voz humana detectada? ──► para TTS, ouve usuário
```

---

## Etapas de implementação

### Etapa 1 — Silero VAD (substitui timeout de silêncio)

**Arquivo:** `src/voice/audio_capture.py` + `src/voice/vad_detector.py` (novo)

- Instalar: `pip install silero-vad`
- Criar `VadDetector` que roda o modelo Silero em chunks de 512 samples
- `audio_capture.py`: substituir o loop de silêncio por chamadas ao `VadDetector`
- Resultado: fim de fala detectado em ~100ms em vez de 2s

**Config nova em `.env`:**
```
LUMINA_VAD_AGGRESSIVENESS=2   # 0-3, quanto mais alto mais corta no silêncio
LUMINA_VAD_MIN_SPEECH_MS=300  # ignora frases menores que 300ms
```

**Critério de conclusão:** latência pós-fala < 300ms

---

### Etapa 2 — Barge-in (usuário interrompe Lumina)

**Arquivo:** `src/voice/tts_engine.py` + `main.py`

- Durante o TTS, o VAD continua rodando num thread separado
- Se detectar energia de voz acima do threshold, emite evento `barge_in`
- `tts_engine.py`: suporta `stop()` chamado de outra thread
- `main.py`: no `_speak()`, registra listener de barge-in que cancela o TTS

**Consideração:** edge-tts toca via `playsound`. Precisará trocar para `sounddevice`
(já no requirements) para ter controle de parar no meio.

**Critério de conclusão:** falar durante a Lumina para ela imediatamente

---

### Etapa 3 — TTS streaming (começa falar antes de gerar tudo)

**Arquivo:** `src/voice/tts_engine.py`

- `edge-tts` já suporta `stream()` que retorna chunks de MP3
- Converter chunks para PCM e tocar via `sounddevice` enquanto novos chunks chegam
- Latência perceptível cai de ~800ms para ~200ms (só o primeiro chunk)

**Critério de conclusão:** primeira sílaba sai em menos de 300ms após o LLM responder

---

### Etapa 4 — Modo conversa fluido + controle de escuta

**Arquivo:** `src/voice/command_processor.py`

#### 4a — Sem wake word por N segundos (timeout automático)

- Já existe `in_conversation` + `_conv_last`
- Ampliar: depois de qualquer resposta da Lumina, entrar em modo conversa por 30s
- Dentro desse modo, qualquer fala vai direto (sem precisar dizer "Lumina")
- Se o usuário ficar 30s sem falar, volta a exigir wake word silenciosamente
- Timeout configurável: `LUMINA_CONV_TIMEOUT_SECONDS=30`

#### 4b — Comando explícito de pausa (controle manual)

Quando o usuário não quer ser ouvido — reunião, ligação, conversa com outra pessoa — pode pausar e retomar por voz:

- **Pausar:** "Lumina, para de ouvir" / "Lumina, fica quieta" / "Lumina, silêncio"
  - Lumina responde "Ok, silenciando." e entra em modo surdo
  - Nesse modo: microfone continua capturando, mas tudo é descartado
  - Único comando processado é o de retorno

- **Retomar:** "Lumina, volta" / "Lumina, pode ouvir" / "Lumina, tô aqui"
  - Lumina responde "Voltei." e retoma modo normal

**Implementação:**
- Nova flag `self._muted: bool` no `CommandProcessor`
- No início do `process()`, se `_muted` e o texto não é um comando de retorno → descarta
- Frases de pausa/retorno detectadas antes do VAD normal (não precisam de wake word)
- Persistir estado no processo (não entre reinicializações — se reiniciar, volta ao normal)

**Config nova:**
```
LUMINA_MUTE_PHRASES=para de ouvir,fica quieta,silencio,cala a boca
LUMINA_UNMUTE_PHRASES=volta,pode ouvir,to aqui,lumina
```

#### Combinação dos dois (comportamento final)

```
[Lumina responde] → entra em modo conversa (30s)
      │
      ├─ usuário fala dentro de 30s → responde, reseta timer
      ├─ 30s de silêncio → volta a exigir wake word (silencioso, sem aviso)
      └─ usuário fala "para de ouvir" → modo surdo
                │
                └─ usuário fala "volta" → retoma modo conversa
```

**Critério de conclusão:** 3 trocas sem dizer "Lumina" + "para de ouvir" silencia + "volta" retoma

---

### Etapa 5 — STT parcial (classificação antecipada)

**Arquivo:** `src/voice/speech_recognizer.py`

- `faster-whisper` permite transcrição de chunks enquanto o áudio chega
- Se o texto parcial já bate com FastCommandRouter (ex: "tira print"), dispara imediatamente
- Para o LLM, espera o texto completo (evita classificação errada por frase incompleta)

**Critério de conclusão:** comandos simples respondem antes do usuário terminar a frase

---

## Ordem sugerida de execução

1. **Etapa 1** (Silero VAD) — maior impacto, resolve o delay principal
2. **Etapa 4** (modo conversa) — muda imediatamente a experiência de uso
3. **Etapa 2** (barge-in) — requer trocar playsound por sounddevice
4. **Etapa 3** (TTS streaming) — polimento de latência
5. **Etapa 5** (STT parcial) — otimização avançada

---

## Dependências novas

```
silero-vad>=0.4.0    # VAD neural leve
sounddevice>=0.4.6   # já está no requirements — mas precisa ser usado no TTS também
```

---

## Riscos

| Risco | Mitigação |
|---|---|
| Silero VAD corta início de frases curtas | Ajustar `VAD_MIN_SPEECH_MS` e threshold |
| Barge-in falso positivo (eco do speaker) | Threshold mais alto + só ativa após 500ms de TTS |
| sounddevice incompatível com edge-tts chunks | Testar com buffer de 50ms antes de integrar |
| STT parcial classifica errado | Só FastCommandRouter usa parcial; LLM sempre espera texto completo |
| Modo surdo ativa por acidente | Frases de pausa são longas o suficiente para não ocorrer por acidente |
| Usuário esquece que está no modo surdo | Lumina pode piscar um LED/ícone no systray no futuro; por ora, responde "Estou em silêncio" se ouvir "Lumina" |
