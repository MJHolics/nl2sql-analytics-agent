"""평가 채점 순수 함수 단위 테스트."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.evalutils import answer_matches, row_values  # noqa: E402


class TestRowValues:
    def test_values_only_ignores_keys(self):
        assert row_values({"category": "Jeans"}) == row_values({"x": "Jeans"})

    def test_stringifies(self):
        assert row_values({"n": 100}) == frozenset({"100"})


class TestAnswerMatches:
    def test_exact_single_value(self):
        assert answer_matches([{"n": 100000}], [{"n": 100000}])

    def test_column_name_difference_still_matches(self):
        # 에이전트 별칭 f0_ vs gold max_price, 값 같으면 일치
        assert answer_matches([{"f0_": 903.0}], [{"max_price": 903.0}])

    def test_extra_column_in_agent_still_matches(self):
        # gold 값이 agent 행에 포함되면 추가 컬럼 있어도 정답
        agent = [{"category": "Outerwear & Coats", "revenue": 1364379.1}]
        gold = [{"category": "Outerwear & Coats"}]
        assert answer_matches(agent, gold)

    def test_wrong_value_fails(self):
        assert not answer_matches([{"category": "Jeans"}], [{"category": "Outerwear & Coats"}])

    def test_multi_row_distinct_matching(self):
        agent = [{"c": "A", "v": 1}, {"c": "B", "v": 2}]
        gold = [{"c": "B"}, {"c": "A"}]
        assert answer_matches(agent, gold)

    def test_gold_row_without_match_fails(self):
        agent = [{"c": "A"}]
        gold = [{"c": "A"}, {"c": "B"}]
        assert not answer_matches(agent, gold)
