"""
Cosine Similarity
=================

Calculate semantic similarity between vectors using cosine distance.

Formula:
    similarity = (v1 * v2) / (||v1|| * ||v2||)

Range:
    -1.0 to 1.0
    - 1.0  = Identical vectors
    - 0.0  = Orthogonal (no similarity)
    - -1.0 = Opposite vectors

Usage:
    from metrics import cosine_similarity
    import numpy as np
    
    v1 = np.array([1, 2, 3])
    v2 = np.array([4, 5, 6])
    
    sim = cosine_similarity(v1, v2)
    print(f"Similarity: {sim:.3f}")

Dependencies:
    - numpy: Vector operations
"""

import numpy as np
from typing import Union


def cosine_similarity(
    v1: Union[np.ndarray, list], 
    v2: Union[np.ndarray, list]
) -> float:
    """
    Calculate cosine similarity between two vectors
    
    Args:
        v1: First vector (numpy array or list)
        v2: Second vector (numpy array or list)
    
    Returns:
        Cosine similarity score (-1.0 to 1.0)
    
    Raises:
        ValueError: If vectors have different dimensions
        ZeroDivisionError: If either vector has zero magnitude
    
    Example:
        >>> v1 = [1, 0, 0]
        >>> v2 = [1, 0, 0]
        >>> cosine_similarity(v1, v2)
        1.0
        
        >>> v1 = [1, 0, 0]
        >>> v2 = [0, 1, 0]
        >>> cosine_similarity(v1, v2)
        0.0
    """
    
    # Convert to numpy arrays if needed
    v1 = np.array(v1)
    v2 = np.array(v2)
    
    # Validate dimensions
    if v1.shape != v2.shape:
        raise ValueError(f"Vector dimension mismatch: {v1.shape} vs {v2.shape}")
    
    # Calculate magnitudes
    magnitude_v1 = np.linalg.norm(v1)
    magnitude_v2 = np.linalg.norm(v2)
    
    # Check for zero vectors
    if magnitude_v1 == 0 or magnitude_v2 == 0:
        raise ZeroDivisionError("Cannot compute similarity for zero-magnitude vector")
    
    # Compute cosine similarity
    dot_product = np.dot(v1, v2)
    similarity = float(dot_product / (magnitude_v1 * magnitude_v2))
    
    return similarity


def batch_cosine_similarity(
    vectors: list[np.ndarray], 
    reference: np.ndarray
) -> list[float]:
    """
    Calculate cosine similarity between multiple vectors and a reference
    
    Args:
        vectors: List of vectors to compare
        reference: Reference vector
    
    Returns:
        List of similarity scores
    
    Example:
        >>> vectors = [[1,0,0], [0,1,0], [1,1,0]]
        >>> reference = [1,0,0]
        >>> batch_cosine_similarity(vectors, reference)
        [1.0, 0.0, 0.707...]
    """
    
    return [cosine_similarity(v, reference) for v in vectors]
