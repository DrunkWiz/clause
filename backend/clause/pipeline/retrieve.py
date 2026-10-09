"""Pick the plan clauses worth showing the model. BM25, stdlib only.

An evidence of coverage is about 2,000 clauses. The drafter gets the top few
dozen for the denial at hand, so the prompt stays small and every clause it
can cite is one it actually saw.
"""

from __future__ import annotations

import math
import re
from collections import Counter

from clause.index.model import Clause
from clause.verify.normalise import norm

STOP = set(
    "a an and are as at be been but by for from has have if in into is it its may not of on or our such that the "
    "their them then there these they this to under was we were what when which will with you your".split()
)
_TOKEN = re.compile(r"[a-z0-9]+")
MIN_CHARS = 60  # headers, page numbers and single words are not worth a slot


def tokens(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(norm(text)) if t not in STOP and len(t) > 1]


class BM25:
    def __init__(self, clauses: list[Clause], k1: float = 1.4, b: float = 0.75):
        self.clauses = [c for c in clauses if len(c.text) >= MIN_CHARS]
        self.docs = [Counter(tokens(c.text)) for c in self.clauses]
        self.lengths = [sum(d.values()) for d in self.docs]
        self.avg = sum(self.lengths) / len(self.lengths) if self.lengths else 0.0
        df = Counter(t for d in self.docs for t in d)
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}
        self.k1, self.b = k1, b

    def scores(self, query: str) -> list[float]:
        q = Counter(tokens(query))
        out = []
        for d, length in zip(self.docs, self.lengths):
            s = 0.0
            for t, qf in q.items():
                f = d.get(t)
                if f:
                    s += self.idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * length / (self.avg or 1))) * min(qf, 3)
            out.append(s)
        return out

    def top(self, query: str, k: int) -> list[Clause]:
        ranked = sorted(zip(self.scores(query), range(len(self.clauses))), key=lambda x: (-x[0], x[1]))
        return [self.clauses[i] for s, i in ranked[:k] if s > 0]


def select(clauses: list[Clause], queries: list[str], k_each: int, limit: int) -> list[Clause]:
    """Union of the top `k_each` clauses for each query, in document order,
    capped at `limit`. Several narrow queries beat one long one: the appeal
    process, the exclusion and the definition each get their own slots."""
    bm = BM25(clauses)
    order = {c.clause_id: i for i, c in enumerate(clauses)}
    picked: dict[str, Clause] = {}
    for q in queries:
        for c in bm.top(q, k_each):
            if len(picked) >= limit:
                break
            picked.setdefault(c.clause_id, c)
    return sorted(picked.values(), key=lambda c: order[c.clause_id])
