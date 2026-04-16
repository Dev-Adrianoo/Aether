"""
Gerenciador de conhecimento do Iris usando Obsidian
Armazena interações, screenshots e insights no vault do Obsidian
"""

import asyncio
import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class ObsidianManager:
    """Gerenciador do vault do Obsidian para armazenamento de conhecimento"""

    def __init__(self, vault_path: str, log_folder: str = "Iris"):
        self.vault_path = Path(vault_path)
        self.iris_dir = self.vault_path / log_folder
        self.interactions_dir = self.iris_dir / "Interactions"
        self.screenshots_dir = self.iris_dir / "Screenshots"
        self.insights_dir = self.iris_dir / "Insights"

        self.ensure_directories()

        logger.info(f"ObsidianManager inicializado (vault: {self.vault_path})")

    def ensure_directories(self):
        for directory in [self.iris_dir, self.interactions_dir, self.screenshots_dir, self.insights_dir]:
            directory.mkdir(parents=True, exist_ok=True)

    async def save_interaction(self, data: Dict[str, Any]) -> bool:
        """Salva uma interação no vault do Obsidian"""
        try:
            interaction_type = data.get('type', 'unknown')
            timestamp = data.get('timestamp', datetime.now().isoformat())

            safe_timestamp = timestamp.replace(':', '-').replace('.', '-')
            filename = f"{interaction_type}_{safe_timestamp}.md"
            filepath = self.interactions_dir / filename

            content = self._format_interaction_markdown(data)

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)

            logger.debug(f"Interação salva: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Erro ao salvar interação: {e}")
            return False

    def _format_interaction_markdown(self, data: Dict[str, Any]) -> str:
        """Formata dados de interação em markdown"""
        interaction_type = data.get('type', 'unknown')
        timestamp = data.get('timestamp', datetime.now().isoformat())

        content = f"""---
type: interaction
interaction_type: {interaction_type}
timestamp: {timestamp}
---

# Interação: {interaction_type}

**Data/Hora:** {timestamp}

"""

        if interaction_type == 'voice_command':
            content += f"""
## Comando de Voz

**Texto:** {data.get('text', 'N/A')}
**Confiança:** {data.get('confidence', 'N/A')}

### Análise
- Tipo: {self._classify_command(data.get('text', ''))}
- Palavras-chave: {self._extract_keywords(data.get('text', ''))}
"""
        elif interaction_type == 'screenshot':
            content += f"""
## Screenshot

**Resumo:** {data.get('summary', 'N/A')}
**Dimensões:** {data.get('dimensions', 'N/A')}

### Análise
- Tem erros: {data.get('has_errors', False)}
- Precisa atenção: {data.get('needs_attention', False)}
- Significância da mudança: {data.get('change_significance', 'low')}
"""
        elif interaction_type == 'openclaude_response':
            content += f"""
## Resposta OpenClaude

**Pergunta/Contexto:** {data.get('context', 'N/A')}

### Resposta
{data.get('response', 'N/A')}

### Insights
{data.get('insights', 'Nenhum insight')}
"""

        content += f"""

---

## Metadados Completos

```json
{json.dumps(data, indent=2, ensure_ascii=False)}
```
"""

        return content

    def _classify_command(self, text: str) -> str:
        """Classifica comando de voz"""
        text_lower = text.lower()

        if any(word in text_lower for word in ['tela', 'print', 'screenshot', 'foto', 'captura', 'mostra', 'olha']):
            return 'screenshot'
        elif any(word in text_lower for word in ['para', 'pare', 'stop', 'encerra']):
            return 'stop'
        elif any(word in text_lower for word in ['ajuda', 'help', 'comandos']):
            return 'help'
        elif any(word in text_lower for word in ['status', 'como', 'tá']):
            return 'status'
        else:
            return 'unknown'

    def _extract_keywords(self, text: str) -> str:
        """Extrai palavras-chave do texto"""
        keywords = ['tela', 'print', 'screenshot', 'foto', 'captura', 'mostra', 'olha',
                   'para', 'pare', 'stop', 'encerra', 'ajuda', 'help', 'status']
        found = [word for word in keywords if word in text.lower()]
        return ', '.join(found) if found else 'Nenhuma'

    async def save_screenshot_metadata(self, screenshot_data: Dict[str, Any], analysis: Dict[str, Any]) -> bool:
        """Salva metadados de screenshot no Obsidian"""
        try:
            timestamp = screenshot_data.get('timestamp', datetime.now().isoformat())
            safe_timestamp = timestamp.replace(':', '-').replace('.', '-')
            filename = f"screenshot_{safe_timestamp}.md"
            filepath = self.screenshots_dir / filename

            content = f"""---
type: screenshot
timestamp: {timestamp}
dimensions: {screenshot_data.get('dimensions', (0, 0))}
---

# Screenshot: {timestamp}

**Dimensões:** {screenshot_data.get('dimensions', (0, 0))}

## Análise

**Resumo:** {analysis.get('summary', 'Sem resumo')}
**Elementos Detectados:** {len(analysis.get('detected_elements', []))}

### Status
- Tem erros: {analysis.get('has_errors', False)}
- Precisa atenção: {analysis.get('needs_attention', False)}
- Significância da mudança: {analysis.get('change_significance', 'low')}

### Elementos Detectados
"""

            for element in analysis.get('detected_elements', []):
                content += f"- {element}\n"

            content += f"""

---

## Metadados Completos

### Screenshot Data
```json
{json.dumps(screenshot_data, indent=2, ensure_ascii=False)}
```

### Análise
```json
{json.dumps(analysis, indent=2, ensure_ascii=False)}
```
"""

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)

            logger.info(f"Metadados de screenshot salvos: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Erro ao salvar metadados de screenshot: {e}")
            return False

    async def save_insight(self, title: str, content: str, tags: Optional[list] = None) -> bool:
        """Salva um insight no vault do Obsidian"""
        try:
            timestamp = datetime.now().isoformat()
            safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
            filename = f"{safe_title}.md"
            filepath = self.insights_dir / filename

            tag_list = tags or []
            tag_list.append('iris')
            tag_list.append('insight')

            formatted_content = f"""---
title: {title}
created: {timestamp}
tags: {', '.join(tag_list)}
---

# {title}

**Criado em:** {timestamp}

{content}

---

*Insight gerado automaticamente pelo Iris*
"""

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(formatted_content)

            logger.info(f"Insight salvo: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Erro ao salvar insight: {e}")
            return False

    async def get_recent_interactions(self, limit: int = 10) -> list:
        """Obtém interações recentes"""
        try:
            interactions = []
            for file in sorted(self.interactions_dir.glob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True):
                if len(interactions) >= limit:
                    break

                with open(file, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Extrair metadados básicos
                interactions.append({
                    'file': file.name,
                    'path': str(file),
                    'content_preview': content[:200] + '...' if len(content) > 200 else content
                })

            return interactions

        except Exception as e:
            logger.error(f"Erro ao obter interações recentes: {e}")
            return []

    async def shutdown(self):
        logger.info("ObsidianManager encerrado")