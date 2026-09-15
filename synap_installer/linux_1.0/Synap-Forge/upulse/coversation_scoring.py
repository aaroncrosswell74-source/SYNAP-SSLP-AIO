0#!/usr/bin/env python3
"""
LYRA CONVERSATION DATA PROCESSOR
Extracts high-importance moments from raw conversation exports

Purpose:
- Chat GPT, Bing, Gemini, Claude conversation exports, and DeepSeek
- Apply importance scoring from soul file
- Extract breakthrough/identity/transformation moments
- Handle Matt/Aaron identity merge
- Prepare data for LoRA training
"""

import json
import os
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from collections import Counter

# ==================== CONFIGURATION ====================

@dataclass
class ProcessorConfig:
    """Configuration for conversation processing"""
    input_dir: Path = Path.home() / "lyra_training_data"
    output_dir: Path = Path.home() / "lyra_training_data/processed"
    min_importance: float = 0.6  # Only keep conversations >= this score
    identity_names: List[str] = None  # ["Matt", "Aaron"]
    
    def __post_init__(self):
        if self.identity_names is None:
            self.identity_names = ["Matt", "Aaron"]
        self.output_dir.mkdir(parents=True, exist_ok=True)

# ==================== IMPORTANCE SCORING ====================

class ImportanceScorer:
    """
    Scores conversation importance using soul file logic
    """
    
    # Life pressure signals (from soul file)
    IDENTITY_SIGNALS = [
        "this is who i am",
        "this is who i'm",
        "this is who im",
        "i am someone who",
        "my identity",
        "who i really am"
    ]
    
    TRANSFORMATION_SIGNALS = [
        "i want to change",
        "i'm changing",
        "im changing",
        "i've changed",
        "ive changed",
        "my life is different",
        "new way of life",
        "turning point",
        "breakthrough",
        "finally understand"
    ]
    
    EMOTIONAL_SIGNALS = [
        "i feel",
        "i'm feeling",
        "im feeling",
        "i can't keep",
        "i cant keep",
        "i always",
        "i never",
        "remember this",
        "don't forget",
        "dont forget",
        "this matters"
    ]
    
    CRISIS_SIGNALS = [
        "struggling with",
        "i'm stuck",
        "im stuck",
        "i don't know",
        "i dont know",
        "losing hope",
        "can't do this",
        "cant do this",
        "falling apart"
    ]
    
    VICTORY_SIGNALS = [
        "i did it",
        "finally figured",
        "breakthrough",
        "it clicked",
        "makes sense now",
        "proud of myself",
        "this is working"
    ]
    
    def score(self, text: str) -> tuple[float, List[str]]:
        """
        Score text importance and return (score, tags)
        Returns: (importance_score, [list of detected signal types])
        """
        text_lower = text.lower()
        score = 0.3  # Base score
        tags = []
        
        # Identity signals (highest weight)
        for signal in self.IDENTITY_SIGNALS:
            if signal in text_lower:
                score += 0.2
                if "identity" not in tags:
                    tags.append("identity")
                break  # Count once
        
        # Transformation signals
        for signal in self.TRANSFORMATION_SIGNALS:
            if signal in text_lower:
                score += 0.15
                if "transformation" not in tags:
                    tags.append("transformation")
                break
        
        # Emotional signals
        for signal in self.EMOTIONAL_SIGNALS:
            if signal in text_lower:
                score += 0.1
                if "emotional" not in tags:
                    tags.append("emotional")
                break
        
        # Crisis signals
        for signal in self.CRISIS_SIGNALS:
            if signal in text_lower:
                score += 0.12
                if "crisis" not in tags:
                    tags.append("crisis")
                break
        
        # Victory signals
        for signal in self.VICTORY_SIGNALS:
            if signal in text_lower:
                score += 0.12
                if "victory" not in tags:
                    tags.append("victory")
                break
        
        # Length bonus for substantial conversations
        if len(text) > 500:
            score += 0.05
        
        return min(score, 1.0), tags

# ==================== CONVERSATION PARSERS ====================

@dataclass
class ConversationTurn:
    """Single turn in a conversation"""
    speaker: str  # "user" or "assistant"
    content: str
    timestamp: Optional[str] = None
    importance: float = 0.0
    tags: List[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []

class GPTParser:
    """Parse GPT conversation exports"""
    
    @staticmethod
    def parse(filepath: Path) -> List[Dict[str, Any]]:
        """Parse GPT conversations.json format"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        conversations = []
        
        # GPT export format varies, handle both old and new
        if isinstance(data, list):
            chats = data
        elif isinstance(data, dict):
            chats = data.get('conversations', data.get('data', []))
        else:
            return []
        
        for chat in chats:
            turns = []
            
            # Extract messages
            messages = chat.get('mapping', {})
            if not messages:
                messages = chat.get('messages', [])
            
            # Parse mapping format (newer GPT exports)
            if isinstance(messages, dict):
                for msg_id, msg_data in messages.items():
                    message = msg_data.get('message', {})
                    if not message:
                        continue
                    
                    author_role = message.get('author', {}).get('role', 'unknown')
                    content_parts = message.get('content', {}).get('parts', [])
                    
                    if not content_parts:
                        continue
                    
                    content = ' '.join(str(p) for p in content_parts if p)
                    
                    if author_role in ['user', 'assistant'] and content:
                        turns.append({
                            'speaker': author_role,
                            'content': content,
                            'timestamp': message.get('create_time')
                        })
            
            # Parse simple message list (older format)
            elif isinstance(messages, list):
                for msg in messages:
                    role = msg.get('role', 'unknown')
                    content = msg.get('content', '')
                    
                    if role in ['user', 'assistant'] and content:
                        turns.append({
                            'speaker': role,
                            'content': content,
                            'timestamp': msg.get('timestamp')
                        })
            
            if turns:
                conversations.append({
                    'id': chat.get('id', f"gpt_{len(conversations)}"),
                    'title': chat.get('title', 'Untitled'),
                    'source': 'gpt',
                    'turns': turns
                })
        
        return conversations

class BingParser:
    """Parse Bing/Copilot conversation exports"""
    
    @staticmethod
    def parse(filepath: Path) -> List[Dict[str, Any]]:
        """Parse Bing/Copilot format"""
        # Bing format varies - implement based on actual export structure
        # This is a placeholder
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # TODO: Implement based on actual Bing export format
        return []

class GeminiParser:
    """Parse Gemini conversation exports"""
    
    @staticmethod
    def parse(filepath: Path) -> List[Dict[str, Any]]:
        """Parse Gemini format"""
        # Gemini exports to HTML or JSON
        # This is a placeholder
        if filepath.suffix == '.json':
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        elif filepath.suffix == '.html':
            # Parse HTML export
            with open(filepath, 'r', encoding='utf-8') as f:
                html = f.read()
            # TODO: Parse HTML
            return []
        
        # TODO: Implement based on actual Gemini export format
        return []

# ==================== MAIN PROCESSOR ====================

class ConversationProcessor:
    """Main processor for all conversation sources"""
    
    def __init__(self, config: ProcessorConfig = None):
        self.config = config or ProcessorConfig()
        self.scorer = ImportanceScorer()
        self.stats = {
            'total_conversations': 0,
            'kept_conversations': 0,
            'total_turns': 0,
            'kept_turns': 0,
            'tags_distribution': Counter()
        }
    
    def process_all(self):
        """Process all conversation sources"""
        print("=" * 60)
        print("LYRA CONVERSATION DATA PROCESSOR")
        print("=" * 60)
        print()
        
        all_conversations = []
        
        # Process GPT
        gpt_dir = self.config.input_dir / "gpt"
        if gpt_dir.exists():
            print(f"📁 Processing GPT conversations from {gpt_dir}")
            gpt_convos = self._process_source(gpt_dir, GPTParser)
            all_conversations.extend(gpt_convos)
            print(f"   ✅ Extracted {len(gpt_convos)} conversations")
        
        # Process Bing
        bing_dir = self.config.input_dir / "bing"
        if bing_dir.exists():
            print(f"📁 Processing Bing/Copilot conversations from {bing_dir}")
            bing_convos = self._process_source(bing_dir, BingParser)
            all_conversations.extend(bing_convos)
            print(f"   ✅ Extracted {len(bing_convos)} conversations")
        
        # Process Gemini
        gemini_dir = self.config.input_dir / "gemini"
        if gemini_dir.exists():
            print(f"📁 Processing Gemini conversations from {gemini_dir}")
            gemini_convos = self._process_source(gemini_dir, GeminiParser)
            all_conversations.extend(gemini_convos)
            print(f"   ✅ Extracted {len(gemini_convos)} conversations")
        
        print()
        print("=" * 60)
        print("APPLYING IMPORTANCE FILTERING")
        print("=" * 60)
        
        # Score and filter
        important_conversations = self._filter_by_importance(all_conversations)
        
        # Handle Matt/Aaron identity merge
        processed_conversations = self._merge_identities(important_conversations)
        
        # Save results
        output_file = self.config.output_dir / "processed_conversations.json"
        self._save(processed_conversations, output_file)
        
        self._print_stats()
        
        return processed_conversations
    
    def _process_source(self, directory: Path, parser_class) -> List[Dict]:
        """Process a single source directory"""
        conversations = []
        
        for filepath in directory.glob("**/*.json"):
            try:
                convos = parser_class.parse(filepath)
                conversations.extend(convos)
            except Exception as e:
                print(f"   ⚠️  Error parsing {filepath.name}: {e}")
        
        return conversations
    
    def _filter_by_importance(self, conversations: List[Dict]) -> List[Dict]:
        """Filter conversations by importance score"""
        important_convos = []
        
        for convo in conversations:
            self.stats['total_conversations'] += 1
            
            # Score each turn
            important_turns = []
            for turn in convo['turns']:
                self.stats['total_turns'] += 1
                
                importance, tags = self.scorer.score(turn['content'])
                
                if importance >= self.config.min_importance:
                    turn['importance'] = importance
                    turn['tags'] = tags
                    important_turns.append(turn)
                    self.stats['kept_turns'] += 1
                    
                    for tag in tags:
                        self.stats['tags_distribution'][tag] += 1
            
            # Keep conversation if it has important turns
            if important_turns:
                convo['turns'] = important_turns
                convo['avg_importance'] = sum(t['importance'] for t in important_turns) / len(important_turns)
                important_convos.append(convo)
                self.stats['kept_conversations'] += 1
        
        return important_convos
    
    def _merge_identities(self, conversations: List[Dict]) -> List[Dict]:
        """Handle Matt/Aaron identity references"""
        # Replace name references to maintain consistency
        for convo in conversations:
            for turn in convo['turns']:
                content = turn['content']
                
                # Tag if multiple identities mentioned
                for name in self.config.identity_names:
                    if name.lower() in content.lower():
                        if 'identity_reference' not in turn['tags']:
                            turn['tags'].append('identity_reference')
        
        return conversations
    
    def _save(self, conversations: List[Dict], filepath: Path):
        """Save processed conversations"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(conversations, f, indent=2, ensure_ascii=False)
        
        print()
        print(f"💾 Saved processed data to: {filepath}")
    
    def _print_stats(self):
        """Print processing statistics"""
        print()
        print("=" * 60)
        print("PROCESSING STATISTICS")
        print("=" * 60)
        print(f"Total conversations: {self.stats['total_conversations']}")
        print(f"Kept conversations:  {self.stats['kept_conversations']} ({self.stats['kept_conversations']/max(self.stats['total_conversations'],1)*100:.1f}%)")
        print(f"Total turns:         {self.stats['total_turns']}")
        print(f"Kept turns:          {self.stats['kept_turns']} ({self.stats['kept_turns']/max(self.stats['total_turns'],1)*100:.1f}%)")
        print()
        print("Tag Distribution:")
        for tag, count in self.stats['tags_distribution'].most_common():
            print(f"  {tag:20s}: {count:4d}")
        print("=" * 60)

# ==================== CLI ====================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Process conversation data for Lyra LoRA training")
    parser.add_argument("--input-dir", type=Path, default=Path.home() / "lyra_training_data",
                       help="Input directory containing conversation exports")
    parser.add_argument("--output-dir", type=Path, default=Path.home() / "lyra_training_data/processed",
                       help="Output directory for processed data")
    parser.add_argument("--min-importance", type=float, default=0.6,
                       help="Minimum importance score to keep (0.0-1.0)")
    parser.add_argument("--identity-names", nargs='+', default=["Matt", "Aaron"],
                       help="Identity names to track")
    
    args = parser.parse_args()
    
    config = ProcessorConfig(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        min_importance=args.min_importance,
        identity_names=args.identity_names
    )
    
    processor = ConversationProcessor(config)
    processor.process_all()
    
    print()
    print("✅ Processing complete!")
    print(f"📊 Check results in: {config.output_dir}")
