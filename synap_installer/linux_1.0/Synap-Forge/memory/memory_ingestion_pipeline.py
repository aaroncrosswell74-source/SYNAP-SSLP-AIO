# memory_ingestion_pipeline.py

class MemoryIngestionPipeline:
    def __init__(self):
        self.relevance_threshold = 0.75
        self.novelty_threshold = 0.60
        self.confidence_threshold = 0.80
        
    def process_incoming(self, memory_payload):
        """
        Incoming Memory
        ↓
        Relevance Score
        ↓
        Novelty Score
        ↓
        Confidence Score
        ↓
        Store / Reject
        """
        
        # 1. RELEVANCE SCORE - Does this relate to existing context?
        relevance = self.calculate_relevance(memory_payload)
        if relevance < self.relevance_threshold:
            return {"action": "reject", "reason": "low_relevance", "score": relevance}
        
        # 2. NOVELTY SCORE - Is this new information?
        novelty = self.calculate_novelty(memory_payload)
        if novelty < self.novelty_threshold:
            # Low novelty - could still store with lower priority
            priority = "low"
        else:
            priority = "high"
        
        # 3. CONFIDENCE SCORE - How reliable is this information?
        confidence = self.calculate_confidence(memory_payload)
        if confidence < self.confidence_threshold:
            return {
                "action": "quarantine", 
                "reason": "low_confidence", 
                "score": confidence,
                "requires_human_review": True
            }
        
        # 4. STORE - with metadata
        return {
            "action": "store",
            "priority": priority,
            "scores": {
                "relevance": relevance,
                "novelty": novelty,
                "confidence": confidence
            },
            "memory": memory_payload
        }