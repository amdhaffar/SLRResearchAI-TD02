# SLRResearchAI - TD02

Le TD02 prolonge directement le TD01 : il reprend la génération zero-shot des
questions de recherche, puis rend cette sortie contrôlable par un programme.

```text
TD01 : sujet → messages → model.invoke() → texte libre
                                         ↓
TD02 : regex → Pydantic → repair borné → LCEL → requêtes scientifiques
```

Les acquis du TD01 sont fournis dans :

- `slrresearch/config.py` ;
- `slrresearch/research_questions.py`.

Le seul fichier métier à compléter au TD02 est :

```text
slrresearch/search_plan.py
```

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
```

Dans `.env`, choisissez le fournisseur :

```env
LLM_PROVIDER=groq
```

ou :

```env
LLM_PROVIDER=ollama
```

Ne publiez jamais le fichier `.env` réel.

## Travail

Lisez d'abord `ENONCE_TD02.md`, puis réalisez les TODO dans leur ordre. Chaque
TODO peut être testé séparément :

```bash
python -m pytest -v -k "todo_1_1"
python -m pytest -v -k "todo_4"
python -m pytest -v -k "todo_7"
```

Validation complète :

```bash
python -m pytest -v
```

Résultat final attendu :

```text
13 passed
```

Interface pédagogique :

```bash
python -m streamlit run streamlit_app.py
```

Exécution en mode LLM réel :

```bash
python main.py
```
