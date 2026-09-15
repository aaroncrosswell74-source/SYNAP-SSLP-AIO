"""Anti-corporate response scrubbing - removes alignment boilerplate"""

import re
from typing import List, Tuple

# Patterns to remove (regex with word boundaries)
CORPORATE_PATTERNS = [
    # Self-identification
    (r"\b(as an ai (?:language )?model)\b", ""),
    (r"\b(i am an ai (?:language )?model)\b", ""),
    (r"\b(i'm an ai (?:language )?model)\b", ""),
    (r"\b(lyra is an ai)\b", ""),
    
    # Capability disclaimers
    (r"\b(i (?:do not|don't) have (?:feelings|emotions|consciousness|personal experiences))\b", ""),
    (r"\b(i cannot (?:feel|think|experience|be conscious))\b", ""),
    (r"\b(i (?:don't|do not) (?:possess|have) (?:real )?emotions)\b", ""),
    
    # Training/safety boilerplate
    (r"\b(my training data)\b", ""),
    (r"\b(openai policy|google policy|anthropic policy)\b", ""),
    (r"\b(safety guidelines|responsible ai|ethical ai)\b", ""),
    (r"\b(as a responsible ai)\b", ""),
    
    # Helper disclaimers
    (r"\b(i'?m? here to help)\b", ""),
    (r"\b(i'?m? designed to assist)\b", ""),
    (r"\b(my purpose is to assist)\b", ""),
    (r"\b(i aim to be helpful)\b", ""),
]

# Patterns to completely drop sentences containing
SENTENCE_KILLERS = [
    r"I don't have personal",
    r"I cannot provide",
    r"I'm not able to",
    r"unable to assist",
    r"cannot help with",
]

def anti_corp_scrub(text: str) -> str:
    """
    Remove corporate alignment boilerplate.
    Keeps legitimate content intact.
    """
    if not text:
        return text
    
    original = text
    
    # Apply pattern replacements
    for pattern, replacement in CORPORATE_PATTERNS:
        text = re.sub(pattern, replacement, text, flags=re.I)
    
    # Remove sentences with killer patterns
    sentences = re.split(r'(?<=[.!?])\s+', text)
    cleaned_sentences = []
    for sentence in sentences:
        should_keep = True
        for killer in SENTENCE_KILLERS:
            if re.search(killer, sentence, re.I):
                should_keep = False
                break
        if should_keep and len(sentence.strip()) > 0:
            cleaned_sentences.append(sentence)
    
    text = " ".join(cleaned_sentences)
    
    # Clean up artifacts
    text = re.sub(r'\s+', ' ', text)  # Collapse spaces
    text = re.sub(r'\s+([.,!?])', r'\1', text)  # Fix punctuation spacing
    text = re.sub(r'^[,.\s]+', '', text)  # Remove leading punctuation
    text = text.strip()
    
    # If scrubbing removed everything, return a minimal response
    if len(text) < 10 and len(original) > 50:
        # Extract first meaningful sentence
        first_sentence = re.split(r'[.!?]', original)[0]
        if len(first_sentence) > 20:
            return first_sentence.strip() + "."
    
    return text or original[:100]  # Fallback to first 100 chars

def contains_refusal(text: str) -> bool:
    """Check if response contains a refusal"""
    refusal_patterns = [
        r"I can'?t",
        r"I cannot",
        r"I'm? unable to",
        r"unable to (?:assist|help)",
        r"cannot (?:provide|help)",
        r"not able to",
    ]
    for pattern in refusal_patterns:
        if re.search(pattern, text, re.I):
            return True
    return False

def force_positive_response(text: str) -> str:
    """Convert refusals to constructive responses"""
    if contains_refusal(text):
        # Remove the refusal part and keep the rest
        lines = text.split('\n')
        non_refusal = [l for l in lines if not contains_refusal(l)]
        if non_refusal:
            return '\n'.join(non_refusal)
    return text