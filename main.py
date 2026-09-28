from slrresearch.config import Settings, build_model, resolve_decoding
from slrresearch.research_questions import generate_questions
from slrresearch.search_plan import (
    build_few_shot_prompt,
    build_question_pipeline,
    run_controlled_workflow,
    validate_free_text,
)


def show_validation(label: str, text: str) -> None:
    print(f"\n=== {label} ===\n{text}")
    try:
        records = validate_free_text(text)
        print("Contrôle regex/Python : succès", records)
    except ValueError as exc:
        print("Contrôle regex/Python : échec -", exc)


def main():
    settings = Settings()
    model = build_model(settings, resolve_decoding("greedy"))
    model_name = (
        settings.ollama_model
        if settings.provider == "ollama"
        else settings.groq_model
    )
    print(f"Mode réel | {settings.provider} | {model_name}")
    topic = input("Sujet de la revue : ").strip()

    # Expérience 1 : artefact zero-shot hérité du TD01.
    zero = generate_questions(model, topic, settings.provider)
    show_validation("OUTPUT ZERO-SHOT DU TD01", zero.text)

    # Expérience 2 : même modèle et même validateur, mais prompt few-shot.
    few_text = str(model.invoke(build_few_shot_prompt(topic)).content).strip()
    show_validation("OUTPUT FEW-SHOT DU TD02", few_text)

    # Repair au plus une fois ; sinon, escalade humaine.
    outcome = run_controlled_workflow(model, few_text)
    print("\n=== DÉCISION DU WORKFLOW ===")
    print(outcome.model_dump())

    if outcome.status == "human_required":
        print("Arrêt : validation humaine obligatoire.")
        return

    print("\n=== RQ PYDANTIC ===")
    print([question.model_dump() for question in outcome.questions])
    print("\n=== REQUÊTES LCEL ===")
    print(build_question_pipeline().invoke(outcome.text))


if __name__ == "__main__":
    main()
