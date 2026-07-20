"""의미 기반 캐시 — 순수 로직 단위테스트(네트워크·임베더 불필요, 결정적 벡터)."""
from __future__ import annotations

from app.semantic_cache import SemanticCache, cosine


def test_cosine():
    assert abs(cosine([1, 0], [1, 0]) - 1.0) < 1e-9
    assert abs(cosine([1, 0], [0, 1]) - 0.0) < 1e-9
    assert cosine([0, 0], [1, 1]) == 0.0


def test_exact_and_paraphrase_hit():
    c = SemanticCache(threshold=0.95)
    c.put([1.0, 0.0, 0.0], "RESULT_A")
    assert c.get([1.0, 0.0, 0.0]) == "RESULT_A"          # 정확 일치
    # 패러프레이즈(거의 같은 방향, 코사인 ~0.9988) → 히트
    assert c.get([0.98, 0.02, 0.0]) == "RESULT_A"
    # 무관(직교) → 미스
    assert c.get([0.0, 1.0, 0.0]) is None
    assert c.hits == 2 and c.misses == 1


def test_threshold_blocks_weak_similarity():
    c = SemanticCache(threshold=0.99)
    c.put([1.0, 0.0], "A")
    assert c.get([0.8, 0.6]) is None                     # cos 0.8 < 0.99 → 미스
    assert abs(c.hit_rate - 0.0) < 1e-9


def test_lru_eviction_by_size():
    c = SemanticCache(threshold=0.99, max_size=2)
    c.put([1, 0, 0], "A")
    c.put([0, 1, 0], "B")
    c.put([0, 0, 1], "C")                                # A 제거(가장 오래됨)
    assert c.get([1, 0, 0]) is None
    assert c.get([0, 1, 0]) == "B" and c.get([0, 0, 1]) == "C"


def test_ttl_expiry():
    clock = {"t": 1000.0}
    c = SemanticCache(threshold=0.99, ttl=10.0, now_fn=lambda: clock["t"])
    c.put([1, 0], "A")
    clock["t"] = 1005.0
    assert c.get([1, 0]) == "A"                          # 5초 < 10초 TTL → 히트
    clock["t"] = 1020.0
    assert c.get([1, 0]) is None                         # 20초 > 10초 → 만료


def test_semantic_beats_exact_on_paraphrases():
    """의미 캐시가 정확일치 캐시보다 패러프레이즈에서 히트율이 높은지(핵심 가치)."""
    # 같은 의미의 5개 패러프레이즈 벡터(거의 같은 방향) + 1개 무관
    base = [1.0, 0.0, 0.0]
    paraphrases = [[1.0, 0.02 * i, 0.0] for i in range(5)]
    exact_keys = {tuple(base): "A"}
    sem = SemanticCache(threshold=0.9)
    sem.put(base, "A")
    exact_hits = sem_hits = 0
    for q in paraphrases:
        if tuple(q) in exact_keys:
            exact_hits += 1
        if sem.get(q) is not None:
            sem_hits += 1
    assert sem_hits > exact_hits                          # 의미 캐시가 더 많이 히트
