import math
import hashlib
import re
from typing import List

STOP_WORDS = {
    'the', 'is', 'a', 'an', 'and', 'or', 'in', 'on', 'at', 'to', 'for', 'of',
    'with', 'my', 'your', 'this', 'that', 'it', 'from', 'as', 'by', 'be', 'are'
}

def generate_dense_embedding(text: str, dim: int = 768) -> List[float]:
    words = re.findall(r'\b\w+\b', text.lower())
    if not words:
        return [0.0] * dim

    vec = [0.0] * dim
    for w in words:
        weight = 0.2 if w in STOP_WORDS else 2.0
        h = int(hashlib.sha256(w.encode('utf-8')).hexdigest(), 16)
        for d in range(8):
            bucket = (h + d * 97) % dim
            sign = 1.0 if ((h >> (d + 8)) & 1) else -1.0
            vec[bucket] += sign * weight

        for n in (3, 4):
            for i in range(len(w) - n + 1):
                gram = w[i:i+n]
                hg = int(hashlib.md5(gram.encode('utf-8')).hexdigest(), 16)
                for d in range(4):
                    bucket_g = (hg + d * 67) % dim
                    sign_g = 1.0 if ((hg >> (d + 4)) & 1) else -1.0
                    vec[bucket_g] += sign_g * 0.5 * weight

    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0:
        vec = [x / norm for x in vec]
    return vec

def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)
