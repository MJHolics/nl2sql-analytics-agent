"""마트 DDL 템플릿 렌더링·문장 분리(순수 로직) 단위테스트 — 네트워크 불필요."""
from __future__ import annotations

import os

from app.mart import render_ddl, split_statements

_MART_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "mart")


def test_render_substitutes_placeholders():
    out = render_ddl(
        "FROM `{SOURCE}.order_items` INTO `{MART}.x`",
        source="proj.public",
        mart="me.nl2sql_mart",
    )
    assert "proj.public.order_items" in out
    assert "me.nl2sql_mart.x" in out
    assert "{SOURCE}" not in out and "{MART}" not in out


def test_split_drops_comments_and_blanks():
    sql = """
    -- 주석
    CREATE VIEW a AS SELECT 1;

    -- 또 주석
    CREATE VIEW b AS SELECT 2;
    """
    stmts = split_statements(sql)
    assert len(stmts) == 2
    assert stmts[0].startswith("CREATE VIEW a")
    assert "주석" not in "".join(stmts)


def test_split_ignores_trailing_semicolon():
    assert len(split_statements("SELECT 1;")) == 1
    assert split_statements(";;  ;") == []


def test_real_ddl_files_render_and_split():
    """배포되는 실제 DDL이 자리표시자 치환 후 정상 분리되는지(개수 sanity)."""
    for fname, min_stmts in [("staging.sql", 5), ("marts.sql", 3), ("quality_checks.sql", 1)]:
        text = open(os.path.join(_MART_DIR, fname), encoding="utf-8").read()
        rendered = render_ddl(text, source="bigquery-public-data.thelook_ecommerce", mart="me.nl2sql_mart")
        stmts = split_statements(rendered)
        assert len(stmts) >= min_stmts, f"{fname}: {len(stmts)} statements"
        assert "{SOURCE}" not in rendered and "{MART}" not in rendered
