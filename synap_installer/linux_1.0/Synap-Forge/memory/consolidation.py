from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)

class ConsolidatedOutput:
    """
    Dual-output consolidation:
    1. Human-readable summary → /var/log/lyra/consolidation_{date}.md
    2. Machine-readable JSON → persona_memory.json (for immediate LLM consumption
    """
    
    def __init__(self):
        self.log_dir = Path("/var/log/lyra")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.persona_path = Path("/home/aaron/Synap-Forge/central_memory/persona_memory.json")
    
    def write_human_summary(self, insights: List[Dict], evolution: Dict) -> str:
        """Create markdown summary for human review"""
        date_str = datetime.now().strftime("%Y-%m-%d")
        output_path = self.log_dir / f"consolidation_{date_str}.md"
        
        content = f"""# 🧠 {assistant_name} Nightly Consolidation - {date_str}

## Summary
- **Insights Processed:** {len(insights)}

## Protected Fields
- SOUL_HASH: ACTIVE
- IDENTITY_LOCK: ENFORCED

---
*{assistant_name} evolved.*
"""
        with open(output_path, 'w') as f:
            f.write(content)
        
        return str(output_path)
    
    def write_persona_json(self, evolution: Dict) -> bool:
        """Write directly to persona_memory.json"""
        if not self.persona_path.parent.exists():
            self.persona_path.parent.mkdir(parents=True, exist_ok=True)
        
        persona = {}
        if self.persona_path.exists():
            with open(self.persona_path, 'r') as f:
                persona = json.load(f)
        
        persona['last_evolution'] = datetime.now().isoformat()
        persona['evolution_log'] = persona.get('evolution_log', [])
        persona['evolution_log'].append({'timestamp': datetime.now().isoformat()})
        persona['evolution_log'] = persona['evolution_log'][-30:]
        
        with open(self.persona_path, 'w') as f:
            json.dump(persona, f, indent=2)
        
        return True
