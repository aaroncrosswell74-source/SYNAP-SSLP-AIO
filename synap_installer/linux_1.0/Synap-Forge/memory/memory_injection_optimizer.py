# memory_injection_optimizer.py

class MemoryInjectionOptimizer:
    def __init__(self):
        self.max_injections = 5
        self.summarizer = LLMSummarizer()  # Or use a smaller model
        self.ranker = MemoryRanker()
        
    def prepare_injection(self, query: str, retrieved_memories: List[Memory]):
        """
        retrieve
        ↓
        summarize
        ↓
        rank
        ↓
        inject
        """
        
        # 1. SUMMARIZE each memory to reduce token count
        summarized = []
        for memory in retrieved_memories:
            summary = self.summarizer.summarize(
                memory.content,
                max_tokens=50  # Keep summaries small
            )
            summarized.append({
                "original": memory,
                "summary": summary,
                "relevance": memory.relevance_score
            })
        
        # 2. RANK by relevance + recency + importance
        ranked = self.ranker.rank(
            summarized,
            query=query,
            weights={
                "relevance": 0.5,
                "recency": 0.3,
                "importance": 0.2
            }
        )
        
        # 3. SELECT top-k for injection
        top_memories = ranked[:self.max_injections]
        
        # 4. FORMAT for injection (compact format)
        injection_text = self._format_injection(top_memories)
        
        return {
            "injection": injection_text,
            "total_tokens_saved": self._calculate_token_savings(retrieved_memories, top_memories),
            "metadata": {
                "original_count": len(retrieved_memories),
                "injected_count": len(top_memories),
                "compression_ratio": len(injection_text) / sum(len(m.content) for m in retrieved_memories)
            }
        }
    
    def _format_injection(self, top_memories):
        """Compact format to minimize token usage"""
        # Example: "[M1] key_point | [M2] key_point | [M3] key_point"
        return " | ".join([
            f"[{i+1}] {m['summary']}" 
            for i, m in enumerate(top_memories)
        ])