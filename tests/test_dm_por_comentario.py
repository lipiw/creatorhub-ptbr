"""Testes da DM automatica por comentario (politica de texto e modelos)."""
from sqlmodel import Session, SQLModel, create_engine, select

from app.models import CommentRule, CommentTask, DmSentLog
from app.platforms.facebook.dm_policy import find_forbidden_terms, validate_dm_templates


def test_termos_proibidos_detectados():
    assert "cura" in find_forbidden_terms("Essa CURA funciona")
    assert "emagrece" in find_forbidden_terms("Emagrece rápido")
    assert find_forbidden_terms("Oi {nick}, responde SIM que eu te mando o link") == []


def test_validacao_templates():
    assert validate_dm_templates([]) != ""
    assert validate_dm_templates(["x" * 700]) != ""
    assert "diabetes" in validate_dm_templates(["controle a diabetes"])
    assert validate_dm_templates(["Oi! Responde SIM e eu te passo o link."]) == ""


def test_modelos_e_unicidade_dm():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(CommentRule(platform="facebook", action="dm", account_id=1))
        s.add(CommentTask(platform="facebook", kind="dm", target_user_id="42"))
        s.add(DmSentLog(account_id=1, commenter_id="42"))
        s.commit()
        assert s.exec(select(CommentTask.kind)).first() == "dm"
        s.add(DmSentLog(account_id=1, commenter_id="42"))
        try:
            s.commit()
            raise AssertionError("deveria violar a unicidade (account_id, commenter_id)")
        except AssertionError:
            raise
        except Exception:
            s.rollback()
