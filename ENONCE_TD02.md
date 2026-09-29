# TD02 - Du texte libre au workflow contrôlé

## 1. Mission

Le TD01 a produit trois questions de recherche sous forme de texte libre avec
un appel LLM zero-shot. Ce texte est lisible par un humain, mais il ne constitue
pas encore une interface fiable pour un programme.

Dans ce TD, vous allez construire le flux suivant :

```text
sortie LLM
   ↓
contrôle textuel par regex et règles Python
   ↓
contrat de données Pydantic
   ↓
composition LCEL vers des requêtes booléennes
```

Lorsqu'une sortie n'est pas conforme, le workflow applique explicitement :

```text
échec → un repair LLM → revalidation
                         ├── conforme → poursuivre
                         └── invalide → validation humaine
```

Le caractère probabiliste du LLM n'est pas supprimé. Son utilisation est
encadrée par un contrat et par des branches déterministes.

## 2. Objectifs pédagogiques

À la fin du TD, vous devez savoir :

1. distinguer texte libre, données structurées et contrat de données ;
2. utiliser une regex pour contrôler et extraire une forme textuelle ;
3. utiliser Pydantic pour valider des champs, types et contraintes ;
4. expliquer pourquoi few-shot améliore la conformité sans la garantir ;
5. déclencher un repair LLM seulement après un échec observé ;
6. revalider une sortie réparée avec le même contrat ;
7. escalader vers un humain après l'échec du repair borné ;
8. composer des transformations déterministes avec LCEL.

## 3. Fichiers

### Relation avec le TD01

Le TD02 ne redemande pas de reconstruire l'appel LLM du TD01. Les fonctions
suivantes sont reprises telles quelles et déjà complètes :

```text
build_system_prompt()
build_user_prompt()
build_zero_shot_messages()
generate_questions()
```

Elles se trouvent dans `slrresearch/research_questions.py`. Leur résultat
`FreeTextQuestions.text` constitue l'entrée du TD02. Les étudiants modifient
uniquement `slrresearch/search_plan.py`.

Fichier principal à compléter :

```text
slrresearch/search_plan.py
```

Fichiers fournis et à lire, mais à ne pas modifier :

- `slrresearch/research_questions.py` : acquis complet du TD01 ;
- `slrresearch/config.py` : sélection Groq/Ollama et décodage ;
- `main.py` : exécution en ligne de commande ;
- `streamlit_app.py` : visualisation des branches ;
- `tests/test_td02.py` : contrat exécutable de chaque TODO.

## 4. Les quatre cas pédagogiques

L'interface propose des cas contrôlés afin que tous les étudiants observent les
mêmes phénomènes, même si un vrai LLM répond différemment.

### Cas A - zero-shot conforme

```text
RQ1. Comment les LLM améliorent-ils le rappel du screening ?
RQ2. Quel contrôle humain doit-il être conservé ?
RQ3. Quelles métriques évaluent-elles cette amélioration ?
```

Le contrôle doit réussir.

### Cas B - zero-shot non conforme

```text
Voici mes propositions :
1. Les LLM améliorent-ils le screening ?
2. Quel contrôle humain conserver ?
3. Comment évaluer la qualité ?
```

Le texte est compréhensible par un humain, mais ne respecte pas le contrat
`RQ1.`, `RQ2.`, `RQ3.`.

### Cas C - few-shot conforme

La réponse suit exactement les exemples du prompt. Le même validateur réussit.

### Cas D - few-shot encore non conforme

```text
Voici les trois questions demandées :
RQ1. Comment les LLM améliorent-ils le rappel du screening ?
RQ2. Quel contrôle humain doit-il être conservé ?
RQ3. Quelles métriques évaluent-elles cette amélioration ?
```

Le texte parasite suffit à provoquer un échec. Le few-shot influence la
génération ; il ne remplace pas la validation.

---

# Partie A - Contrôler la forme textuelle

Dans cette partie, vous n'utilisez ni Pydantic ni LLM. Vous appliquez une regex
et des règles Python déterministes.

## TODO 1.1 - Extraire les lignes utiles

**Fichier :** `slrresearch/search_plan.py`

```python
def extract_non_empty_lines(text: str) -> list[str]:
```

À réaliser : nettoyer le texte avec `strip()`, le découper avec `splitlines()`,
nettoyer chaque ligne, ignorer les lignes vides et lever
`ValueError("Texte vide")` si nécessaire.

```python
lines = [
    line.strip()
    for line in text.strip().splitlines()
    if line.strip()
]
if not lines:
    raise ValueError("Texte vide")
return lines
```

```bash
python -m pytest -v -k "todo_1_1"
```

## TODO 1.2 - Contrôler une ligne par regex

```python
def parse_rq_line(line: str) -> dict:
```

La regex `RQ_PATTERN` est fournie. Utilisez :

```python
match = RQ_PATTERN.fullmatch(line)
```

Si `match` vaut `None`, levez une `ValueError` contenant la ligne fautive.
Sinon, retournez :

```python
{
    "identifier": match.group(1),
    "question": match.group(2).strip(),
}
```

```bash
python -m pytest -v -k "todo_1_2"
```

## TODO 1.3 - Contrôler les identifiants

```python
def validate_identifiers(records: list[dict]) -> None:
```

Construisez la liste des identifiants puis comparez-la exactement à :

```python
["RQ1", "RQ2", "RQ3"]
```

Levez `ValueError` si les listes diffèrent.

```bash
python -m pytest -v -k "todo_1_3"
```

## TODO 1.4 - Refuser les doublons

```python
def validate_no_duplicates(records: list[dict]) -> None:
```

### Ce que signifie « doublon »

On refuse le résultat dès que **deux questions possèdent exactement la même
formulation**, même si leurs identifiants sont différents. Par exemple :

```python
[
    {"identifier": "RQ1", "question": "Quel est le rôle du LLM ?"},
    {"identifier": "RQ2", "question": "Quel est le rôle du LLM ?"},
    {"identifier": "RQ3", "question": "Comment évaluer le système ?"},
]
```

doit être refusé parce que les textes de RQ1 et RQ2 sont identiques.

### Pourquoi utiliser un `set` ?

Une liste conserve toutes les valeurs, y compris les répétitions :

```python
questions = ["Question A", "Question A", "Question B"]
len(questions)  # 3
```

Un `set` ne conserve qu'une occurrence de chaque valeur :

```python
unique_questions = set(questions)
len(unique_questions)  # 2
```

Une différence entre les deux longueurs prouve donc qu'au moins deux questions
sont identiques.

### Algorithme demandé

1. construire la liste de toutes les valeurs `record["question"]` ;
2. construire un `set` à partir de cette liste ;
3. calculer `len(questions)` et `len(unique_questions)` ;
4. si les longueurs sont différentes, lever une `ValueError` ;
5. sinon, ne rien retourner explicitement : la fonction termine normalement.

### Squelette à compléter

```python
def validate_no_duplicates(records: list[dict]) -> None:
    questions = [record["question"] for record in records]
    unique_questions = set(________________)

    if len(________________) != len(________________):
        raise ValueError("Les trois questions doivent être différentes")
```

Les trois blancs utilisent uniquement les variables `questions` et
`unique_questions`. Il n'est pas nécessaire d'écrire une double boucle.

Dans ce TD, l'égalité est exacte après le nettoyage déjà effectué par
`parse_rq_line()`. La gestion avancée des majuscules, accents ou paraphrases ne
fait pas partie de ce TODO.

```bash
python -m pytest -v -k "todo_1_4"
```

Le test construit volontairement deux dictionnaires ayant le même champ
`question` et vérifie qu'une `ValueError` est levée.

## TODO 1.5 - Composer le contrôle textuel

```python
def validate_free_text(text: str) -> list[dict]:
```

Enchaînez : extraction des lignes, parsing de chaque ligne, contrôle des
identifiants, contrôle des doublons, puis retour des dictionnaires. N'appelez
ni Pydantic ni le LLM dans cette fonction.

```bash
python -m pytest -v -k "todo_1_5"
```

### Point de contrôle A

```bash
python -m pytest -v -k "todo_1"
python -m streamlit run streamlit_app.py
```

Exécutez A et B, puis répondez :

1. B est-il faux scientifiquement ou seulement non conforme ?
2. Pourquoi rendre la regex plus permissive affaiblirait-il le contrat ?
3. Contrôlons-nous ici la forme, le type ou la pertinence ?

---

# Partie B - Influencer la génération avec few-shot

## TODO 2 - Construire le prompt few-shot

```python
def build_few_shot_prompt(topic: str) -> str:
```

Le prompt doit contenir l'instruction de produire exactement trois questions,
l'interdiction d'ajouter introduction, conclusion ou JSON, deux exemples
complets `Sujet → RQ1/RQ2/RQ3`, le sujet courant et la forme littérale
`RQ1.`, `RQ2.`, `RQ3.`.

```python
clean = topic.strip()
if not clean:
    raise ValueError("Sujet vide")

return f"""Propose exactement trois questions de recherche.
N'ajoute ni introduction, ni conclusion, ni JSON.

Exemple 1 - Sujet : ...
RQ1. ...
RQ2. ...
RQ3. ...

Exemple 2 - Sujet : ...
RQ1. ...
RQ2. ...
RQ3. ...

Sujet courant : {clean}
Retourne exactement trois lignes RQ1., RQ2. et RQ3."""
```

```bash
python -m pytest -v -k "todo_2"
```

Dans Streamlit, comparez C et D sans modifier le validateur.

---

# Partie C - Réparer uniquement après un échec

## TODO 3 - Construire le prompt de repair

**Fichier à modifier :** `slrresearch/search_plan.py`

### Pourquoi ce TODO existe-t-il ?

Dans le cas D, le validateur reçoit par exemple :

```text
Voici les trois questions demandées :
RQ1. Comment les LLM améliorent-ils le rappel du screening ?
RQ2. Quel contrôle humain doit-il être conservé ?
RQ3. Quelles métriques évaluent-elles cette amélioration ?
```

La première ligne provoque une erreur proche de :

```text
Ligne non conforme : Voici les trois questions demandées :
```

Le repair ne doit pas inventer de nouvelles questions. Il doit recevoir la
sortie refusée et la cause précise du refus, puis corriger uniquement sa forme.

### Fonction à compléter

```python
def build_repair_prompt(text: str, error: str) -> str:
```

Cette fonction construit seulement une chaîne de caractères. Elle ne doit pas :

- appeler `model.invoke()` ;
- appeler le validateur ;
- supprimer directement une ligne avec Python ;
- modifier elle-même le texte reçu.

Elle doit retourner un prompt qui contient obligatoirement :

1. l'objectif : corriger uniquement la forme ;
2. l'interdiction de modifier le sens des questions ;
3. l'erreur exacte reçue dans `error` ;
4. le contrat attendu : exactement trois lignes `RQ1.`, `RQ2.`, `RQ3.` ;
5. l'interdiction d'ajouter introduction, explication, Markdown ou JSON ;
6. un exemple complet de sortie conforme ;
7. le texte réellement rejeté, contenu dans `text`.

### Squelette à compléter

Complétez les parties indiquées sans recopier une réponse fixe propre au cas D :

```python
def build_repair_prompt(text: str, error: str) -> str:
    return f"""Tu corriges la forme d'une sortie destinée à un programme.

[TÂCHE]
Corrige uniquement ________________________________.
Préserve _________________________________________.

[ERREUR DÉTECTÉE]
{error}

[CONTRAT ATTENDU]
- Exactement ____________________________________.
- Chaque ligne commence par ______________________.
- N'ajoute ni ___________________________________.

[EXEMPLE CONFORME]
RQ1. Comment l'IA influence-t-elle la personnalisation pédagogique ?
RQ2. Quels risques l'IA introduit-elle dans l'évaluation ?
RQ3. Quel contrôle humain doit-il être conservé ?

[TEXTE À CORRIGER]
{text}

[SORTIE]
Retourne uniquement ______________________________."""
```

Les expressions `{error}` et `{text}` ne sont pas du texte décoratif : ce sont
les deux entrées variables de la fonction. Le test vérifiera qu'elles se
retrouvent réellement dans le prompt retourné.

### Code déjà fourni : effectuer un seul appel

Ne modifiez pas cette fonction :

```python
def repair_with_llm(model, text: str, error: str) -> str:
    response = model.invoke(build_repair_prompt(text, error))
    return str(response.content).strip()
```

Le déroulement est donc :

```text
text + error
     ↓
build_repair_prompt()     ← votre TODO 3
     ↓
model.invoke(...)         ← code fourni, un seul appel
     ↓
response.content.strip()
     ↓
nouveau texte à revalider ← réalisé dans le TODO 7
```

### Vérification 1 - Inspecter le prompt sans appeler de LLM

Depuis la racine du TD :

```bash
python -c "from slrresearch.search_plan import build_repair_prompt; print(build_repair_prompt('Voici mes propositions :', 'Ligne non conforme'))"
```

Vérifiez visuellement que le texte et l'erreur apparaissent, ainsi que le
contrat et l'exemple.

### Vérification 2 - Exécuter le test ciblé

```bash
python -m pytest -v -k "todo_3"
```

Le test utilise un faux modèle reproductible. Il vérifie :

- que le prompt contient `text` et `error` ;
- que `repair_with_llm()` appelle le modèle exactement une fois ;
- que la réponse retournée peut ensuite passer par `validate_free_text()`.

### Vérification 3 - Observer le scénario D

Dans Streamlit :

1. choisissez `Cas contrôlés du TD` ;
2. exécutez d'abord le cas A pour accéder à l'étape few-shot ;
3. sélectionnez `D - few-shot encore non conforme` ;
4. cliquez sur `2 - Exécuter et valider le few-shot` ;
5. observez la ligne rejetée et le verdict `NON CONFORME` ;
6. cliquez sur `3 - Corriger avec le LLM puis revalider`.

La case `Simuler un repair encore invalide` contrôle uniquement le résultat
pédagogique du repair :

- case décochée puis bouton 3 : le repair devient conforme et le statut affiché
  est `REPAIRED` ;
- case cochée puis bouton 3 : le repair reste invalide et le statut affiché est
  `human_required`.

Après avoir coché ou décoché la case, cliquez obligatoirement de nouveau sur le
bouton 3. Les TODO 4, 5 et 6 sont exécutés seulement à l'étape 4 et ne doivent
donc pas empêcher l'observation du TODO 3.

### Erreurs fréquentes

- retourner une chaîne fixe qui ne contient ni `{text}` ni `{error}` ;
- appeler le LLM dans `build_repair_prompt()` ;
- demander de « régénérer de meilleures questions », ce qui modifie le sens ;
- retirer le validateur après la réparation ;
- lancer plusieurs réparations sans condition d'arrêt ;
- demander du JSON alors que le contrat courant exige trois lignes textuelles.

À retenir : valider détecte un problème ; réparer produit une nouvelle
proposition ; revalider décide si cette proposition peut être utilisée.

---

# Partie D - Valider le contrat Pydantic

## TODO 4 - Construire les objets `ResearchQuestion`

**Fichier à modifier :** `slrresearch/search_plan.py`

### Point de départ

Après le contrôle regex, `validate_free_text()` retourne des dictionnaires :

```python
[
    {
        "identifier": "RQ1",
        "question": "Comment les LLM améliorent-ils le screening ?",
    },
    # RQ2 et RQ3...
]
```

Ces dictionnaires ont une structure pratique, mais Python ne garantit pas encore
qu'ils contiennent les bons champs et des valeurs acceptables. Le modèle fourni
définit ce contrat :

```python
class ResearchQuestion(BaseModel):
    identifier: str = Field(pattern=r"^RQ[0-9]+$")
    question: str = Field(min_length=15)
```

Pydantic vérifiera donc :

- la présence de `identifier` et `question` ;
- leur type `str` ;
- la forme de l'identifiant ;
- la longueur minimale de la question.

### Fonction à compléter

```python
def validate_questions(records: list[dict]) -> list[ResearchQuestion]:
```

**Entrée :** les dictionnaires produits par `validate_free_text()`.

**Sortie :** une liste d'objets `ResearchQuestion` validés.

Pour chaque dictionnaire, utilisez :

```python
ResearchQuestion.model_validate(record)
```

Complétez le squelette suivant :

```python
def validate_questions(records: list[dict]) -> list[ResearchQuestion]:
    questions = []

    for record in records:
        question = ______________________________
        questions.append(_______________________)

    return __________________
```

Ne capturez pas `ValidationError`. Une donnée invalide doit remonter à
l'orchestrateur, qui décidera ensuite de réparer ou d'escalader.

### Vérification

```bash
python -m pytest -v -k "todo_4"
```

Le test doit accepter les trois dictionnaires conformes et refuser :

```python
{"identifier": "RQ1", "question": "Trop court"}
```

### Erreurs fréquentes

- retourner les dictionnaires sans appeler `model_validate()` ;
- valider uniquement le premier dictionnaire ;
- appeler un LLM dans cette fonction ;
- capturer silencieusement l'erreur et retourner une liste vide.

À retenir : la regex contrôle la forme textuelle ; Pydantic valide le contrat
des données extraites.

---

# Partie E - Transformer les RQ en requêtes

## TODO 5 - Construire la requête booléenne

**Fichier à modifier :** `slrresearch/search_plan.py`

### Objectif

Les objets `ResearchQuestion` indiquent ce que la revue cherche à étudier. Le
futur `SearchAgent` a cependant besoin d'une requête booléenne. Le dictionnaire
fourni sépare deux dimensions :

```python
SEARCH_CONCEPTS = {
    "task": [
        "systematic review screening",
        "study selection",
        "title and abstract screening",
    ],
    "technology": [
        "large language models",
        "LLM",
        "generative AI",
    ],
}
```

Règle de construction :

- `AND` relie deux concepts différents : une tâche et une technologie ;
- `OR` relie les synonymes ou formulations alternatives ;
- 3 tâches × 3 technologies produisent exactement 9 couples.

```python
def build_queries(questions: list[ResearchQuestion]) -> dict[str, str]:
```

**Précondition :** `questions` ne doit pas être vide. Levez `ValueError` si
c'est le cas. La liste prouve que le contrat scientifique précédent a été
validé, même si les formulations ne sont pas directement concaténées ici.

Chaque couple prend exactement la forme :

```text
("terme task" AND "terme technology")
```

### Algorithme guidé

```text
1. vérifier que questions n'est pas vide
2. lire SEARCH_CONCEPTS["task"]
3. lire SEARCH_CONCEPTS["technology"]
4. pour chaque task :
       pour chaque technology :
           construire ("task" AND "technology")
5. joindre les 9 couples avec " OR "
6. retourner la requête pour scholar, ieee et acm
```

### Squelette à compléter

```python
def build_queries(questions: list[ResearchQuestion]) -> dict[str, str]:
    if not questions:
        raise ValueError("Au moins une RQ validée est nécessaire")

    combinations = []
    for task in SEARCH_CONCEPTS["task"]:
        for technology in SEARCH_CONCEPTS["technology"]:
            expression = f'("{________}" AND "{____________}")'
            combinations.append(________________)

    base_query = " OR ".join(________________)

    return {
        "scholar": __________,
        "ieee": __________,
        "acm": __________,
    }
```

À ce stade, les trois moteurs reçoivent la même expression. L'adaptation à la
syntaxe particulière de chaque moteur sera la responsabilité des outils du
`SearchAgent` au TD03.

### Résultat attendu

Le début doit être :

```text
("systematic review screening" AND "large language models") OR
("systematic review screening" AND "LLM") OR ...
```

La requête complète doit contenir 8 opérateurs `OR` entre 9 couples et 9
opérateurs `AND`.

```bash
python -m pytest -v -k "todo_5"
```

### Erreurs fréquentes

- utiliser `OR` entre la tâche et la technologie ;
- ne produire que trois couples au lieu du produit cartésien de neuf couples ;
- oublier les guillemets autour des expressions ;
- construire une requête différente sans justification pour chaque moteur ;
- accepter silencieusement une liste de questions vide.

## TODO 6 - Composer la chaîne LCEL

**Fichier à modifier :** `slrresearch/search_plan.py`

### Objectif

Les trois fonctions sont déjà utilisables séparément :

```text
validate_free_text : str → list[dict]
validate_questions : list[dict] → list[ResearchQuestion]
build_queries       : list[ResearchQuestion] → dict[str, str]
```

La sortie de chaque étape correspond exactement à l'entrée de la suivante.
LCEL permet de décrire cette séquence avec l'opérateur `|`.

```python
def build_question_pipeline():
```

Une fonction Python ordinaire ne supporte pas directement la composition LCEL.
Enveloppez-la d'abord dans :

```python
RunnableLambda(nom_de_la_fonction)
```

### Squelette à compléter

```python
def build_question_pipeline():
    text_control = RunnableLambda(__________________)
    data_contract = RunnableLambda(__________________)
    query_builder = RunnableLambda(__________________)

    return __________ | __________ | __________
```

L'ordre est obligatoire : on ne peut pas appliquer Pydantic au texte brut et on
ne peut pas construire les requêtes avant d'avoir les objets validés.

### Comment exécuter la chaîne ?

```python
pipeline = build_question_pipeline()
queries = pipeline.invoke(text_conforme)
```

Ici, `invoke()` exécute la chaîne LCEL complète. Ce n'est pas un nouvel appel
LLM : les trois composants sont des fonctions Python déterministes.

```bash
python -m pytest -v -k "todo_6"
```

Le résultat doit être un dictionnaire possédant exactement les clés :

```python
{"scholar", "ieee", "acm"}
```

### Erreurs fréquentes

- composer les fonctions dans le mauvais ordre ;
- oublier `RunnableLambda` ;
- appeler les fonctions pendant la construction, par exemple
  `RunnableLambda(validate_free_text(text))` ;
- confondre `pipeline.invoke(...)` avec un appel LLM ;
- ajouter un agent alors que le chemin est connu à l'avance.

À retenir : LCEL décrit ici une chaîne déterministe, pas un agent autonome.

---

# Partie F - Construire le workflow contrôlé

## TODO 7 - Valider, réparer, revalider ou escalader

**Fichier à modifier :** `slrresearch/search_plan.py`

**Fonction concernée :**

```python
run_controlled_workflow(model, text)
```

### Travail demandé en une phrase

Dans cette fonction, vous devez modifier **exactement trois lignes** :

1. remplacer le premier `None` par l'appel qui contrôle le texte réparé ;
2. remplacer le second `None` par l'appel qui construit les objets Pydantic ;
3. remplacer le mauvais statut `accepted` par le statut d'intervention humaine.

Vous ne devez pas modifier le premier `try`, l'appel à `repair_with_llm()`, les
deux blocs `except` ni les objets `WorkflowOutcome` déjà construits.

### Objectif

Ce TODO ne vous demande pas d'écrire tout le workflow à partir de zéro. Le
chemin nominal, le premier `try/except`, l'appel de repair et la construction
des résultats sont fournis. Vous complétez seulement les décisions essentielles
qui correspondent au cours :

1. appliquer exactement le même contrat au texte réparé ;
2. retourner le statut `repaired` après une revalidation réussie ;
3. retourner le statut `human_required` après le second échec.

```python
def run_controlled_workflow(model, text: str) -> WorkflowOutcome:
```

### Signification de `WorkflowOutcome`

```python
class WorkflowOutcome(BaseModel):
    status: Literal["accepted", "repaired", "human_required"]
    text: str
    questions: list[ResearchQuestion]
    error: str | None
    repair_attempts: int
```

Les trois statuts signifient :

| Statut | Signification |
|---|---|
| `accepted` | Le texte initial est valide ; aucun repair n'est effectué. |
| `repaired` | Le texte initial a échoué ; un repair a réussi après revalidation. |
| `human_required` | Le repair unique a aussi échoué ; le workflow s'arrête. |

### Branches attendues

```text
validate_free_text + validate_questions
   ├── succès → status="accepted", repair_attempts=0
   └── échec  → repair_with_llm une seule fois
                  ↓
               même revalidation
                  ├── succès → status="repaired", repair_attempts=1
                  └── échec  → status="human_required",
                               repair_attempts=1, error renseignée
```

### Code déjà présent dans le fichier

Le fichier étudiant contient désormais ce squelette. Ne réécrivez pas les
parties marquées « Code fourni » :

```python
def run_controlled_workflow(model, text: str) -> WorkflowOutcome:
    try:
        # Code fourni : validation du texte initial.
        records = validate_free_text(text)
        questions = validate_questions(records)
        return WorkflowOutcome(
            status="accepted",
            text=text,
            questions=questions,
            repair_attempts=0,
            error=None,
        )

    except ValueError as first_error:
        # Code fourni : un seul appel de repair.
        repaired_text = repair_with_llm(
            model,
            text,
            str(first_error),
        )

        try:
            # TODO 7.1 : compléter ces deux lignes.
            repaired_records = None
            repaired_questions = None

            return WorkflowOutcome(
                status="repaired",
                text=repaired_text,
                questions=repaired_questions,
                repair_attempts=1,
                error=None,
            )

        except ValueError as second_error:
            # TODO 7.2 : corriger uniquement le statut.
            return WorkflowOutcome(
                status="accepted",  # valeur provisoire incorrecte
                text=repaired_text,
                questions=[],
                repair_attempts=1,
                error=str(second_error),
            )
```

### TODO 7.1 - Compléter les deux lignes de revalidation

#### Où intervenir ?

Repérez exactement ce bloc dans `run_controlled_workflow()` :

```python
repaired_records = None
repaired_questions = None
```

Le texte initial a déjà été refusé et le LLM vient de produire
`repaired_text`. Il ne faut pas faire confiance directement à cette nouvelle
réponse : elle doit traverser les **deux mêmes contrôles** que le texte initial.

Complétez selon le tableau suivant :

| Ligne | Valeur reçue | Fonction à appeler | Résultat obtenu |
|---|---|---|---|
| `repaired_records = ...` | `repaired_text` | `validate_free_text` | `list[dict]` |
| `repaired_questions = ...` | `repaired_records` | `validate_questions` | `list[ResearchQuestion]` |

Squelette à compléter :

```python
repaired_records = validate_free_text(________________)
repaired_questions = validate_questions(________________)
```

Les deux arguments attendus sont déjà disponibles dans la fonction. N'ajoutez
aucun nouvel appel LLM et ne créez pas de nouvelle fonction.

Le chemin à reproduire est donc :

```text
repaired_text
      ↓
validate_free_text(...)
      ↓
validate_questions(...)
```

Si les deux appels réussissent, le `return WorkflowOutcome(...)` fourni juste
après renvoie déjà :

```python
status="repaired"
```

Vous n'avez pas à modifier ce `return`. Vous ne devez ni affaiblir la regex ni
construire un second validateur spécial pour la réparation.

#### Vérification immédiate de 7.1

```bash
python -m pytest -v -k "todo_7_echec_declenche"
```

Le test fournit :

- un texte initial non conforme ;
- un faux LLM qui retourne un texte réparé conforme.

Le résultat attendu est `status == "repaired"` avec exactement un appel du
faux LLM.

### TODO 7.2 - Modifier un seul statut après le second échec

#### Où intervenir ?

Repérez le second bloc `except ValueError as second_error`. Il est exécuté
uniquement lorsque `repaired_text` ne respecte toujours pas le contrat.

Dans ce bloc, remplacez uniquement la valeur provisoire :

```python
status="accepted"
```

par le statut qui signifie « le système s'abstient et demande un humain ».
La classe `WorkflowOutcome` fournit trois valeurs possibles :

```python
"accepted", "repaired", "human_required"
```

Choisissez celle qui correspond à l'intervention humaine. Ne modifiez pas
`questions=[]`, `repair_attempts=1` ou `error=str(second_error)`. Ne rappelez
pas `repair_with_llm()` : une seule tentative est autorisée.

#### Vérification immédiate de 7.2

```bash
python -m pytest -v -k "todo_7_second_echec"
```

Le faux LLM retourne volontairement une réponse encore invalide. Le résultat
attendu est `status == "human_required"`, une erreur renseignée et exactement
un appel du faux LLM.

### Ce que vous ne devez pas écrire

N'ajoutez pas :

- une boucle `while` ;
- un second appel à `repair_with_llm()` ;
- un troisième bloc de validation ;
- un `return` supplémentaire ;
- une correction manuelle du texte avec `replace()`.

Le TODO 7 consiste uniquement à compléter la branche déjà fournie.

### Pourquoi capturer `ValueError` ?

Les fonctions de contrôle textuel lèvent `ValueError`. Les erreurs de validation
Pydantic héritent également de `ValueError`. Le workflow peut donc traiter ces
deux non-conformités sans masquer les erreurs de programmation telles que
`NameError` ou `TypeError`.

### Vérification progressive

Test du chemin nominal, sans repair :

```bash
python -m pytest -v -k "todo_7_sortie_conforme"
```

Test du repair réussi :

```bash
python -m pytest -v -k "todo_7_echec_declenche"
```

Test de l'escalade humaine :

```bash
python -m pytest -v -k "todo_7_second_echec"
```

Puis les trois ensemble :

```bash
python -m pytest -v -k "todo_7"
```

### Résultats attendus

| Entrée | Appels de repair | Statut |
|---|---:|---|
| texte initial conforme | 0 | `accepted` |
| texte invalide, repair conforme | 1 | `repaired` |
| texte invalide, repair invalide | 1 | `human_required` |

### Erreurs fréquentes

- réparer même lorsque le texte initial est conforme ;
- revalider seulement avec la regex sans appliquer Pydantic ;
- utiliser un validateur plus permissif après le repair ;
- oublier `text=repaired_text` dans le résultat ;
- laisser le statut `accepted` après l'échec du repair ;
- appeler plusieurs fois le LLM ;
- utiliser une boucle `while` sans limite.

Après une tentative infructueuse, le workflow s'abstient et demande une
validation humaine. Cette borne rend le coût et le comportement observables.

## 5. Validation finale

```bash
python -m pytest -v
python main.py
python -m streamlit run streamlit_app.py
```

Résultat attendu :

```text
13 passed
```

Dans Streamlit, observez séparément le zero-shot, le contrôle regex, le
few-shot, le repair conditionnel, la revalidation, le contrat Pydantic, les
requêtes LCEL et l'escalade `human_required`.

## 6. Questions de synthèse

1. Pourquoi une sortie lisible peut-elle être inutilisable par un programme ?
2. Quelle différence existe entre regex et Pydantic ?
3. Pourquoi le prompt n'est-il pas un contrat logiciel ?
4. Pourquoi conserver le même validateur pour zero-shot et few-shot ?
5. Pourquoi transmettre l'erreur exacte au repair ?
6. Pourquoi borner le repair à une tentative ?
7. Quand faut-il s'abstenir et demander un humain ?
8. Pourquoi LCEL convient-il à la transformation finale ?
9. Pourquoi ce workflow contrôlé n'est-il pas encore un agent autonome ?
10. Quel artefact sera donné au `SearchAgent` du TD03 ?
