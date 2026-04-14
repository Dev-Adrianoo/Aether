# Aether

A sensory development assistant that sees what you see, hears what you say, and acts in the digital world as an extension of your will.

## What is Aether?

Aether is a sensory development assistant created to overcome human limitations in software development. It integrates computer vision, speech recognition, and text-to-speech with OpenClaude to create a truly contextual programming partner.

Unlike traditional AI assistants that live in a text-only bubble, Aether sees your screen, hears your voice commands, and responds like a human partner.

## Core Philosophy

"An assistant that doesn't see your screen is blind. An assistant that doesn't hear your voice is deaf. An assistant that doesn't speak to you is mute. Aether sees, hears, and speaks - and therefore, acts."

## Architecture

### Sensory System
- **Vision**: Real-time screen analysis with OpenCV and MSS
- **Hearing**: Wake word "Aether" with SpeechRecognition and command processing  
- **Speech**: Natural voice responses with edge-tts and pyttsx3
- **Brain**: Obsidian vault for permanent memory and learning
- **Action**: OpenClaude integration for full system control

### Key Features
- Intelligent screenshot capture (trigger-based and interval-based)
- Context economy - only interrupts when necessary
- Continuous learning through Obsidian documentation
- Autonomous action with human direction

## Getting Started

### Prerequisites
- Python 3.9+
- Windows/Linux/macOS
- Microphone and speakers
- OpenClaude running locally

### Installation

```bash
# Clone the repository
git clone https://github.com/Dev-Adrianoo/Aether.git
cd Aether

# Create virtual environment
python -m venv venv

# Activate on Windows
venv\Scripts\activate

# Activate on Linux/Mac
source venv/bin/activate

# Install dependencies
pip install -r requirements_minimal.txt
```

### Basic Usage

```bash
# Run Aether
python main.py

# Test installation
python tests/run_simple_tests.py

# Run full test suite (requires pytest)
python -m pytest tests/ -v
```

## How It Works

### Vision Module
Captures screenshots intelligently based on:
- Voice triggers: "screen", "print", "screenshot", "photo"
- Time intervals: Every 60 seconds for continuous monitoring
- Error detection: When visual errors are detected

### Hearing Module
Listens for the wake word "Aether" and processes natural commands:
- "Aether, take a screenshot"
- "Aether, show me the screen"
- "Aether, capture this"

### Integration
- Screenshots and context sent to OpenClaude for analysis
- Commands executed through OpenClaude's system control
- All interactions logged to Obsidian for continuous learning

## Project Structure

```
Aether/
├── src/                    # Source code
│   ├── vision/            # Screenshot capture and analysis
│   ├── hearing/           # Speech recognition and processing
│   ├── speech/            # Text-to-speech synthesis
│   ├── integration/       # OpenClaude communication
│   └── brain/             # Obsidian memory system
├── tests/                 # Test suite
│   ├── unit/             # Unit tests
│   ├── integration/      # Integration tests
│   └── e2e/              # End-to-end tests
├── config/               # Configuration files
├── data/                 # Generated data (excluded from git)
└── docs/                 # Documentation
```

## Development

### Running Tests
```bash
# Simple tests (no pytest required)
python tests/run_simple_tests.py

# Full test suite
pip install pytest pytest-asyncio
python -m pytest tests/ -v
```

### Code Style
- Follow PEP 8 conventions
- Use type hints where appropriate
- Write comprehensive docstrings
- Maintain separation between documentation and code

## Documentation

Project documentation follows the LuminaXR pattern in Obsidian:
- `01_Visao_de_Produto/` - Vision and philosophy
- `02_Arquitetura_e_Design/` - Technical architecture
- `03_Mecanicas/` - Features and mechanics
- `Aether_Dev Log/` - Development logs and learnings

## Roadmap

### Phase 1: Sensory Foundation
- Basic screenshot capture with trigger words
- Wake word detection with "Aether"
- Simple voice commands
- OpenClaude integration

### Phase 2: Advanced Features
- Computer vision analysis for error detection
- Natural language command processing
- Emotional speech synthesis
- Learning system in Obsidian

### Phase 3: Optimization
- Machine learning for visual context
- Adaptive speech recognition
- Performance optimization
- Dashboard and monitoring

## Contributing

This is a personal project by Adriano, but feedback and suggestions are welcome through GitHub issues.

## License

Private project - All rights reserved.

## Acknowledgments

- Built as a sensory extension for the LuminaXR project
- Inspired by the need for truly contextual development assistants
- Created to overcome the limitations of text-only AI tools

---

*Aether sees what you see, hears what you say, and acts as an extension of your will in the digital world.*