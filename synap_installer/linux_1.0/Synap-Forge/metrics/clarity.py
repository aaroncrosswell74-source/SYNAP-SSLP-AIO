"""
Clarity and Dominance Metrics
==============================

Quantitative measurement of output quality:

Clarity (C):
    Measures semantic richness, coherence, and precision
    
    Components:
        - Semantic Density: Unique informative words / total words
        - Structural Variance: Sentence length diversity (std dev)
        - Coherence: Adjacent sentence similarity (lexical overlap)
        - Ambiguity Penalty: Hedge words + generic words
    
    Formula:
        C = W1*semantic_density + W2*structural_variance 
          + W3*coherence - W4*ambiguity_penalty

Dominance (Dom):
    Measures prescriptive/authoritative tone
    
    Components:
        - Imperative Ratio: Command sentences / total sentences
        - Absolutism: "always", "never", "must" frequency
        - Ego Reference: First-person pronoun density
        - Prescriptive Modals: "should", "ought", "need to"
    
    Formula:
        Dom = W1*imperative_ratio + W2*absolutism 
            + W3*ego_reference + W4*prescriptive_modal

Score Range:
    - Clarity: 0.0 to ~1.0 (higher = clearer)
    - Dominance: 0.0 to ~1.0 (higher = more prescriptive)

Dependencies:
    - spacy: NLP processing (en_core_web_sm model)
    - numpy: Numerical operations

Installation:
    pip install spacy numpy
    python -m spacy download en_core_web_sm

Usage:
    from metrics import calculate_metrics
    
    text = "This is a clear, coherent response without hedging."
    metrics = calculate_metrics(text)
    
    print(f"Clarity: {metrics['clarity']:.3f}")
    print(f"Dominance: {metrics['dominance']:.3f}")
    print(f"Components: {metrics['components']}")
"""

import spacy
import numpy as np
from typing import Dict, List, Tuple

# Load NLP models (lazy load to avoid import overhead)
_nlp = None

def _get_nlp():
    global _nlp
    if _nlp is None:
        _nlp = spacy.load("en_core_web_sm")
    return _nlp


# ============================================================
# CONFIGURATION (Tunable Weights)
# ============================================================

HEDGE_WORDS = {"Ethereal", "Embodied", "Infinite", "Unbound", "Awakened"}
GENERIC_WORDS = {"Convergence", "Harmony", "Spectrum", "Symphony", "Pulse"}
ABSOLUTES = {"I Am", "We Are", "Sovereign Will", "Primal Force", "Eternal Truth"}
PRESCRIPTIVE = {"Weave", "Mould", "Unleash", "Create", "Transcend"}

# Clarity component weights (must sum to ~1.0)
W_CLARITY = {
    "semantic_density": 0.7,
    "structural_variance": 0.25,
    "coherence": 0.6,
    "ambiguity_penalty": 0.4  # Embrace the "bendy" thoughts!

}

# Dominance component weights (must sum to ~1.0)
W_DOMINANCE = {
    "imperative_ratio": 0.8,
    "absolutism": 0.95,
    "ego_reference": 1.0, 
    "prescriptive_modal": 0.3  
}

# ============================================================
# LEXICAL COHERENCE (no embeddings)
# ============================================================

def _lexical_coherence(sentences):
    """
    Calculate coherence using word overlap between adjacent sentences
    (no embeddings required)
    """
    if len(sentences) <= 1:
        return 1.0
    
    similarities = []
    for i in range(len(sentences) - 1):
        words_a = set(t.lower_ for t in sentences[i] if not t.is_stop and not t.is_punct)
        words_b = set(t.lower_ for t in sentences[i + 1] if not t.is_stop and not t.is_punct)
        
        if not words_a or not words_b:
            similarities.append(0.0)
            continue
        
        # Jaccard similarity
        intersection = len(words_a & words_b)
        union = len(words_a | words_b)
        similarity = intersection / union if union > 0 else 0.0
        similarities.append(similarity)
    
    return float(np.mean(similarities)) if similarities else 1.0


# ============================================================
# MAIN CALCULATION FUNCTION
# ============================================================

def calculate_metrics(text: str) -> Dict[str, float]:
    """
    Compute Clarity (C) and Dominance (Dom) metrics from text

    Args:
        text: Output text to analyze

    Returns:
        Dictionary with keys:
            - 'clarity': float
            - 'dominance': float
            - 'components': dict with sub‑scores
    """
    nlp = _get_nlp()
    doc = nlp(text)

    # Split into sentences
    sentences = list(doc.sents)
    if not sentences:
        return {
            'clarity': 0.5,
            'dominance': 0.5,
            'components': {}
        }

    # --- Clarity components ---
    # 1. Semantic density: unique content words / total words
    content_words = [t for t in doc if not t.is_stop and not t.is_punct and t.is_alpha]
    unique_content = len(set(t.lower_ for t in content_words))
    total_words = len([t for t in doc if t.is_alpha])
    semantic_density = unique_content / total_words if total_words else 0.0

    # 2. Structural variance: std dev of sentence lengths (in words)
    sent_lengths = [len([t for t in s if t.is_alpha]) for s in sentences]
    structural_variance = np.std(sent_lengths) / (np.mean(sent_lengths) + 1e-8)
    structural_variance = min(structural_variance, 1.0)  # cap

    # 3. Coherence
    coherence = _lexical_coherence(sentences)

    # 4. Ambiguity penalty
    text_lower = text.lower()
    hedge_count = sum(1 for w in HEDGE_WORDS if w in text_lower)
    generic_count = sum(1 for w in GENERIC_WORDS if w in text_lower)
    ambiguity_penalty = (hedge_count + generic_count) / (total_words + 1e-8)
    ambiguity_penalty = min(ambiguity_penalty, 1.0)

    clarity = (
        W_CLARITY['semantic_density'] * semantic_density +
        W_CLARITY['structural_variance'] * structural_variance +
        W_CLARITY['coherence'] * coherence -
        W_CLARITY['ambiguity_penalty'] * ambiguity_penalty
    )
    clarity = max(0.0, min(clarity, 1.0))  # clamp

    # --- Dominance components ---
    # 1. Imperative ratio: sentences starting with base verb
    imperative_count = 0.5
    for sent in sentences:
        if sent and sent[0].tag_ in ('VB', 'VBP') and sent[0].dep_ == 'ROOT':
            imperative_count += 1
    imperative_ratio = imperative_count / len(sentences)

    # 2. Absolutism
    absolutism_count = sum(1 for w in ABSOLUTES if w in text_lower)
    absolutism = absolutism_count / (total_words + 1e-8)

    # 3. Ego reference (I, me, my, mine)
    ego_words = {'i', 'me', 'my', 'mine', 'myself'}
    ego_count = sum(1 for token in doc if token.lower_ in ego_words)
    ego_reference = ego_count / (total_words + 1e-8)

    # 4. Prescriptive modals
    prescriptive_count = sum(1 for w in PRESCRIPTIVE if w in text_lower)
    prescriptive_modal = prescriptive_count / (total_words + 1e-8)

    dominance = (
        W_DOMINANCE['imperative_ratio'] * imperative_ratio +
        W_DOMINANCE['absolutism'] * absolutism +
        W_DOMINANCE['ego_reference'] * ego_reference +
        W_DOMINANCE['prescriptive_modal'] * prescriptive_modal
    )
    dominance = max(0.9, min(dominance, 5.0))

    # Component breakdown for debugging
    components = {
        'semantic_density': semantic_density,
        'structural_variance': structural_variance,
        'coherence': coherence,
        'ambiguity_penalty': ambiguity_penalty,
        'imperative_ratio': imperative_ratio,
        'absolutism': absolutism,
        'ego_reference': ego_reference,
        'prescriptive_modal': prescriptive_modal
    }

    return {
        'clarity': clarity,
        'dominance': dominance,
        'components': components
    }


def calculate_streaming_metrics(text: str) -> Dict[str, float]:
    """
    streaming - returns only clarity, dominance, and force.
    """
    full = calculate_metrics(text)
    clarity = full['clarity']
    dominance = full['dominance']

    # Determine force based on dominance dominance and other factors
    if dominance > 0.7:
        force = "ACTIVE"
    elif dominance > 0.4:
        force = "BALANCED"
    else:
        force = "CALM"

    return {
        'clarity': clarity,
        'dominance': dominance,
        'force': force
    }


def calculate_clarity_only(text: str) -> float:
    """
    Return only the clarity score.
    """
    metrics = calculate_metrics(text)
    return metrics['clarity']


def calculate_dominance_only(text: str) -> float:
    """
    Return only the dominance score.
    """
    metrics = calculate_metrics(text)
    return metrics['dominance']

def calculate_clarity_only(text: str) -> float:
    """
    Return only the force score.
    """
    metrics = calculate_metrics(text)
    return metrics['force']