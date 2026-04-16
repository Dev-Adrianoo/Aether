# Lumina

Assistente de desenvolvimento sensorial que vê o que você vê, ouve o que você diz e age no mundo digital como extensão da sua vontade.

## O que é a Lumina?

A Lumina é um assistente de desenvolvimento criado para superar as limitações humanas no desenvolvimento de software. Integra visão computacional, reconhecimento de fala e síntese de voz com OpenClaude para criar uma parceira de programação verdadeiramente contextual.

Diferente de assistentes tradicionais presos a bolhas de texto, a Lumina vê sua tela, ouve seus comandos de voz e responde como uma parceira humana.

## Filosofia

"Um assistente que não vê sua tela é cego. Um que não ouve sua voz é surdo. Um que não fala com você é mudo. A Lumina vê, ouve e fala — e portanto, age."

## Arquitetura

### Sistema Sensorial
- **Visão**: Análise de tela em tempo real com OpenCV e MSS
- **Audição**: Wake word "Lumina" com SpeechRecognition e processamento de comandos
- **Fala**: Respostas por voz naturais com edge-tts e pyttsx3
- **Memória**: Vault Obsidian para memória permanente e aprendizado
- **Ação**: Integração com OpenClaude para controle total do sistema

### Funcionalidades
- Captura de screenshot inteligente (por trigger de voz ou intervalo)
- Economia de contexto — só interrompe quando necessário
- Aprendizado contínuo via documentação no Obsidian
- Ação autônoma com direção humana
- Roteamento LLM — qualquer fala natural é entendida e encaminhada

## Início Rápido

### Pré-requisitos
- Python 3.9+
- Windows/Linux/macOS
- Microfone e alto-falantes
- OpenClaude rodando localmente

### Instalação

```bash
git clone https://github.com/Dev-Adrianoo/lumina-agent.git
cd lumina-agent

python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/Mac

pip install -r requirements.txt
```

### Uso

```bash
# Iniciar a Lumina
python main.py

# Testar instalação
python tests/run_simple_tests.py

# Suite completa de testes (requer pytest)
python -m pytest tests/ -v
```

## Como Funciona

### Módulo de Visão
Captura screenshots com base em:
- Gatilhos de voz: "tela", "print", "screenshot", "foto"
- Intervalo de tempo: a cada 60 segundos para monitoramento contínuo
- Detecção de erros: quando erros visuais são detectados

### Módulo de Audição
Aguarda a wake word "Lumina" e processa comandos naturais:
- "Lumina, tira um print"
- "Lumina, mostra a tela"
- "Lumina, captura isso"

### Integração
- Screenshots e contexto enviados ao LLM para análise
- Comandos executados pelo OpenClaude
- Todas as interações registradas no Obsidian para aprendizado contínuo

## Estrutura do Projeto

```
lumina-agent/
├── src/
│   ├── vision/         # Captura e análise de tela
│   ├── voice/          # Reconhecimento de fala e TTS
│   ├── integrations/   # Comunicação com LLM
│   ├── actions/        # Ações no sistema
│   └── brain/          # Sistema de memória Obsidian
├── tests/
│   ├── unit/
│   ├── integration/
│   └── manual/
├── scripts/            # Scripts utilitários
├── config.py           # Configuração central
├── main.py             # Ponto de entrada
└── data/               # Dados gerados (excluído do git)
```

## Desenvolvimento

### Testes
```bash
python tests/run_simple_tests.py
python -m pytest tests/ -v
```

### Variáveis de Ambiente (`.env`)
```
LUMINA_WAKE_WORD=lumina
OPENCLAUDE_API_KEY=sua_chave
OBSIDIAN_VAULT_PATH=C:/caminho/para/vault
TTS_ENGINE=edge-tts
```

## Documentação

Documentação do projeto no vault Obsidian em `Documentation/Dev-lumina-agent`.

## Licença

Projeto privado — todos os direitos reservados.

---

*A Lumina vê o que você vê, ouve o que você diz e age como extensão da sua vontade no mundo digital.*
