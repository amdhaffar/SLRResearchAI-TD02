from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from slrresearch.search_plan import (
    ResearchQuestion,
    build_few_shot_prompt,
    build_question_pipeline,
    build_queries,
    build_repair_prompt,
    extract_non_empty_lines,
    parse_rq_line,
    repair_with_llm,
    run_controlled_workflow,
    validate_free_text,
    validate_identifiers,
    validate_no_duplicates,
    validate_questions,
)


GOOD = (
    "RQ1. Comment les LLM améliorent-ils le rappel du screening ?\n"
    "RQ2. Quel contrôle humain doit-il être conservé ?\n"
    "RQ3. Quelles métriques évaluent-elles cette amélioration ?"
)
ZERO_SHOT_BAD = (
    "Voici mes propositions :\n"
    "1. Les LLM améliorent-ils le screening ?\n"
    "2. Quel contrôle humain conserver ?\n"
    "3. Comment évaluer la qualité ?"
)
FEW_SHOT_BAD = "Voici les trois questions demandées :\n" + GOOD


class FakeModel:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = 0

    def invoke(self, prompt):
        self.calls += 1
        return SimpleNamespace(content=self.outputs.pop(0))


def test_todo_1_1_extrait_les_lignes_non_vides():
    assert extract_non_empty_lines("\n RQ1. Une question assez longue ? \n\n") == [
        "RQ1. Une question assez longue ?"
    ]
    with pytest.raises(ValueError):
        extract_non_empty_lines("  \n ")


def test_todo_1_2_regex_controle_toute_la_ligne():
    record = parse_rq_line("RQ1. Une question suffisamment longue ?")
    assert record["identifier"] == "RQ1"
    with pytest.raises(ValueError):
        parse_rq_line("Introduction : RQ1. Une question suffisamment longue ?")


def test_todo_1_3_exige_les_trois_identifiants_ordonnes():
    records = [
        {"identifier": "RQ1", "question": "Question suffisamment longue 1"},
        {"identifier": "RQ2", "question": "Question suffisamment longue 2"},
        {"identifier": "RQ3", "question": "Question suffisamment longue 3"},
    ]
    validate_identifiers(records)
    with pytest.raises(ValueError):
        validate_identifiers(records[1:])


def test_todo_1_4_refuse_les_doublons():
    duplicate = "Même question suffisamment longue"
    with pytest.raises(ValueError):
        validate_no_duplicates(
            [
                {"identifier": "RQ1", "question": duplicate},
                {"identifier": "RQ2", "question": duplicate},
            ]
        )


def test_todo_1_5_distingue_cas_zero_shot_a_et_b():
    assert len(validate_free_text(GOOD)) == 3
    with pytest.raises(ValueError):
        validate_free_text(ZERO_SHOT_BAD)


def test_todo_2_prompt_few_shot_contient_deux_exemples():
    prompt = build_few_shot_prompt("LLM et SLR")
    assert prompt.count("Exemple") == 2
    assert "LLM et SLR" in prompt
    assert "RQ1." in prompt and "RQ2." in prompt and "RQ3." in prompt


def test_todo_3_repair_transmet_le_texte_et_erreur_en_un_appel():
    prompt = build_repair_prompt("texte invalide", "format invalide")
    assert "texte invalide" in prompt and "format invalide" in prompt
    model = FakeModel([GOOD])
    assert validate_free_text(
        repair_with_llm(model, "texte invalide", "format invalide")
    )
    assert model.calls == 1


def test_todo_4_pydantic_applique_le_contrat():
    questions = validate_questions(validate_free_text(GOOD))
    assert all(isinstance(question, ResearchQuestion) for question in questions)
    with pytest.raises(ValidationError):
        validate_questions([{"identifier": "RQ1", "question": "Trop court"}])


def test_todo_5_requetes_combinent_or_et_and():
    queries = build_queries(validate_questions(validate_free_text(GOOD)))
    assert set(queries) == {"scholar", "ieee", "acm"}
    query = queries["scholar"]
    assert query.startswith(
        '("systematic review screening" AND "large language models")'
    )
    assert query.endswith(
        '("title and abstract screening" AND "generative AI")'
    )
    assert query.count(" OR ") == 8
    assert query.count(" AND ") == 9


def test_todo_6_lcel_compose_les_trois_transformations():
    result = build_question_pipeline().invoke(GOOD)
    assert set(result) == {"scholar", "ieee", "acm"}


def test_todo_7_sortie_conforme_poursuit_sans_repair():
    model = FakeModel([])
    outcome = run_controlled_workflow(model, GOOD)
    assert outcome.status == "accepted"
    assert outcome.repair_attempts == 0
    assert model.calls == 0


def test_todo_7_echec_declenche_un_repair_puis_revalidation():
    model = FakeModel([GOOD])
    outcome = run_controlled_workflow(model, FEW_SHOT_BAD)
    assert outcome.status == "repaired"
    assert outcome.repair_attempts == 1
    assert model.calls == 1


def test_todo_7_second_echec_escalade_vers_humain():
    model = FakeModel(["réponse encore invalide"])
    outcome = run_controlled_workflow(model, FEW_SHOT_BAD)
    assert outcome.status == "human_required"
    assert outcome.repair_attempts == 1
    assert outcome.error
    assert model.calls == 1
