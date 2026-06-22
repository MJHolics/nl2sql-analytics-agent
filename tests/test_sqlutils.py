"""SQL 순수 함수 단위 테스트 — 네트워크·LLM·BigQuery 없이 실행."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.sqlutils import check_read_only, extract_sql, find_unknown_columns  # noqa: E402


class TestExtractSql:
    def test_fenced_sql_block(self):
        text = "여기 쿼리입니다:\n```sql\nSELECT 1\n```\n끝"
        assert extract_sql(text) == "SELECT 1"

    def test_plain_fence_without_lang(self):
        assert extract_sql("```\nSELECT a FROM t\n```") == "SELECT a FROM t"

    def test_no_fence_returns_trimmed(self):
        assert extract_sql("  SELECT 1 ;  ") == "SELECT 1"

    def test_trailing_semicolon_removed(self):
        assert extract_sql("```sql\nSELECT 1;\n```") == "SELECT 1"


class TestCheckReadOnly:
    def test_select_passes(self):
        assert check_read_only("SELECT * FROM t") is None

    def test_with_cte_passes(self):
        assert check_read_only("WITH x AS (SELECT 1) SELECT * FROM x") is None

    def test_leading_whitespace_ok(self):
        assert check_read_only("\n  SELECT 1") is None

    def test_non_select_rejected(self):
        assert check_read_only("SHOW TABLES") is not None

    def test_delete_rejected(self):
        assert check_read_only("DELETE FROM t") is not None

    def test_drop_rejected(self):
        assert check_read_only("DROP TABLE t") is not None

    def test_select_with_hidden_dml_rejected(self):
        # SELECT로 시작해도 본문에 금지 구문이 있으면 차단
        assert check_read_only("SELECT 1; DROP TABLE t") is not None


class TestFindUnknownColumns:
    KNOWN = {"sale_price", "product_id", "id", "category"}

    def test_all_known(self):
        sql = "SELECT t.sale_price, p.category FROM x t JOIN y p ON t.product_id = p.id"
        assert find_unknown_columns(sql, self.KNOWN) == []

    def test_detects_unknown(self):
        sql = "SELECT t.revenue FROM x t"
        assert find_unknown_columns(sql, self.KNOWN) == ["revenue"]

    def test_skip_set_excludes_token(self):
        sql = "SELECT t.id FROM proj.thelook.orders t"
        assert find_unknown_columns(sql, self.KNOWN, skip={"thelook", "orders"}) == []
