import re

import streamlit as st

from slrresearch.config import Settings,build_model
from slrresearch.research_questions import build_zero_shot_prompt,generate_questions
from slrresearch.search_plan import parse_rq_line,validate_free_text,build_few_shot_prompt,repair_with_llm,validate_questions,build_question_pipeline
TOPIC="Utilisation des LLM pour assister le screening des SLR en génie logiciel"
settings=Settings(); model_name=settings.ollama_model if settings.provider=="ollama" else settings.groq_model
st.set_page_config(page_title="SLRResearchAI · TD02",page_icon=":material/schema:",layout="wide")
st.title("TD02 · Du zero-shot à la réparation conditionnelle")
st.write("Le TD02 reprend la sortie libre du TD01 et l'encadre par un workflow contrôlé.")
st.code("texte libre → regex/Python → Pydantic → LCEL → requêtes\n"
        "                    ↘ échec → repair unique → revalidation → humain",
        language="text")
with st.container(border=True):
 st.subheader("Acquis du TD01 · premier appel LLM en zero-shot")
 st.write("Au TD01, vous avez construit `generate_questions()`. Son prompt contient une instruction et le sujet, mais aucun exemple : c'est du **zero-shot prompting**.")
 st.code(build_zero_shot_prompt(TOPIC),language="text")
 st.caption("L'output de cet appel devient l'entrée de l'étape 1 du TD02. Le TD02 ne repart pas d'un autre problème.")
with st.container(border=True):
 a,b,c=st.columns(3); a.metric("Fournisseur",settings.provider.upper()); b.metric("Modèle",model_name); c.metric("Contrat","RQ1 / RQ2 / RQ3")
mode=st.segmented_control("Source des scénarios",["Cas contrôlés du TD","LLM réel (.env)"],default="Cas contrôlés du TD")
topic=st.text_area("Sujet de la revue",TOPIC,height=90)
st.session_state.setdefault("td02_zero_result",None); st.session_state.setdefault("td02_few_result",None); st.session_state.setdefault("td02_repaired",None); st.session_state.setdefault("td02_final",None); st.session_state.setdefault("td02_human_required",None)
good="RQ1. Comment les LLM améliorent-ils le rappel du screening ?\nRQ2. Quel contrôle humain doit-il être conservé ?\nRQ3. Quelles métriques évaluent-elles cette amélioration ?"
cases={"A — zero-shot conforme":good,"B — zero-shot non conforme":"Voici mes propositions :\n1. Les LLM améliorent-ils le screening ?\n2. Quel contrôle humain conserver ?\n3. Comment évaluer la qualité ?","C — few-shot conforme":good,"D — few-shot encore non conforme":"Voici les trois questions demandées :\n"+good}
def diagnose_lines(text):
 diagnostics=[]
 for number,line in enumerate((x.strip() for x in text.splitlines() if x.strip()),start=1):
  try:
   record=parse_rq_line(line); diagnostics.append({"ligne":number,"statut":"Acceptée","contenu":line,"raison":f'{record["identifier"]} respecte le contrat'})
  except ValueError:
   diagnostics.append({"ligne":number,"statut":"Rejetée","contenu":line,"raison":"Ne respecte pas la forme RQn. question"})
 return diagnostics
def diagnose_expected_rqs(text):
 lines=[line.strip() for line in text.splitlines() if line.strip()]
 results=[]
 for identifier in ("RQ1","RQ2","RQ3"):
  candidates=[line for line in lines if re.match(rf"^{identifier}\b",line)]
  if not candidates:
   results.append({"identifier":identifier,"ok":False,"message":"absente","line":"—","record":None}); continue
  try:
   record=parse_rq_line(candidates[0]); results.append({"identifier":identifier,"ok":True,"message":"forme acceptée par regex ; dictionnaire extrait","line":candidates[0],"record":record})
  except ValueError:
   results.append({"identifier":identifier,"ok":False,"message":"non transformable : séparateur ou syntaxe invalide","line":candidates[0],"record":None})
 return results
def render_experiment(run,title):
 st.subheader(title)
 with st.container(border=True):
  st.caption(run["source"])
  st.write("1. Prompt envoyé au LLM")
  st.code(run["prompt"],language="text")
  st.write("2. Réponse brute retournée par le LLM")
  st.code(run["text"],language="text",wrap_lines=True)
 diagnostics=run["diagnostics"]
 accepted=sum(item["statut"]=="Acceptée" for item in diagnostics)
 rejected=len(diagnostics)-accepted
 st.write("3. Résultat mesurable du contrôle textuel")
 m1,m2,m3,m4=st.columns(4)
 m1.metric("Lignes reçues",len(diagnostics))
 m2.metric("Lignes acceptées",accepted)
 m3.metric("Lignes rejetées",rejected)
 m4.metric("Contrat global","CONFORME" if not run["error"] else "NON CONFORME")
 if rejected:
  st.error("Au moins une ligne parasite ou mal formée est présente : tout le document est refusé, même si RQ1, RQ2 et RQ3 sont individuellement correctes.")
 st.dataframe(diagnostics,hide_index=True)
 st.write("4. Diagnostic individuel des trois RQ attendues")
 rq_columns=st.columns(3)
 for column,item in zip(rq_columns,run["rq_status"]):
  with column:
   if item["ok"]: st.success(f'{item["identifier"]} : forme textuelle acceptée')
   else: st.error(f'{item["identifier"]} : échouée')
   st.code(item["line"],language="text",wrap_lines=True)
   st.caption(item["message"])
   if item["record"]: st.json(item["record"])
 st.write("5. Bilan global")
 if run["error"]:
  st.error("Échec déterministe global : "+run["error"])
 else:
  st.success("Réussite globale : les trois RQ peuvent être transformées.")
st.subheader("Étape 1 · Réutiliser l'output TD01")
st.write("Exécuter le prompt zero-shot acquis, puis soumettre sa réponse au contrôle regex/Python. Pydantic interviendra seulement après cette étape.")
scenario_zero=st.selectbox("Cas TD01 à observer",["A — zero-shot conforme","B — zero-shot non conforme"],key="scenario_zero")
with st.expander("Voir le prompt TD01 pour le sujet courant"):
 try: st.code(build_zero_shot_prompt(topic),language="text")
 except ValueError: st.warning("Saisissez un sujet non vide.")
if st.button("1 · Exécuter TD01 et valider son output",icon=":material/looks_one:",type="primary",key="stage1"):
 st.session_state.td02_repaired=None; st.session_state.td02_final=None
 if mode=="Cas contrôlés du TD": text=cases[scenario_zero]
 else:
  try: text=generate_questions(build_model(settings),topic,settings.provider).text
  except Exception as exc: st.error(str(exc)); text=None
 if text:
  try: records=validate_free_text(text); error=None
  except Exception as exc: records=[]; error=str(exc)
  st.session_state.td02_zero_result={"stage":1,"source":"TD01 · appel LLM avec prompt zero-shot","prompt":build_zero_shot_prompt(topic),"text":text,"records":records,"error":error,"diagnostics":diagnose_lines(text),"rq_status":diagnose_expected_rqs(text)}
  st.session_state.td02_few_result=None
  st.rerun()
if zero:=st.session_state.get("td02_zero_result"):
 render_experiment(zero,"Résultat de l'appel zero-shot (TD01)")
 st.subheader("Étape 2 · Few-shot + même validation")
 st.write("On conserve le même sujet et le même validateur. Seul le prompt évolue : il contient maintenant des exemples.")
 if mode=="Cas contrôlés du TD":
  def reset_few_result():
   st.session_state.td02_few_result=None
   st.session_state.td02_final=None
   st.session_state.td02_human_required=None
  scenario_few=st.selectbox("Scénario contrôlé à exécuter",["C — few-shot conforme","D — few-shot encore non conforme"],key="scenario_few",on_change=reset_few_result)
  st.info("Expérience reproductible : C réussit ; D échoue à cause d'un texte parasite malgré le few-shot. Aucun LLM n'est appelé pour produire C ou D.")
  with st.expander("Voir avant l'exécution la différence injectée entre C et D"):
   left_case,right_case=st.columns(2)
   with left_case:
    st.success("C : 3 lignes reçues, 3 acceptées, 0 rejetée")
    st.code(cases["C — few-shot conforme"],language="text")
   with right_case:
    st.error("D : 4 lignes reçues, 3 acceptées, 1 rejetée")
    st.code(cases["D — few-shot encore non conforme"],language="text")
 else:
  scenario_few=None
  st.warning("Le menu C/D est masqué en mode réel : C et D sont des scénarios pédagogiques prédéfinis, tandis que la réponse du LLM réel n'est pas prédictible. Revenez à « Cas contrôlés du TD » pour les exécuter.")
 if st.button("2 · Exécuter et valider le few-shot",icon=":material/looks_two:",type="primary",key="stage2"):
  st.session_state.td02_repaired=None; st.session_state.td02_final=None; st.session_state.td02_human_required=None
  if mode=="Cas contrôlés du TD":
   text=cases[scenario_few]; source=f"TD02 · simulation contrôlée {scenario_few[0]} — aucun appel LLM"
  else:
   try:
    text=str(build_model(settings).invoke(build_few_shot_prompt(topic)).content).strip(); source=f"TD02 · appel LLM réel {settings.provider.upper()} avec prompt few-shot"
   except Exception as exc: st.error(str(exc)); text=None
  if text:
   try: records=validate_free_text(text); error=None
   except Exception as exc: records=[]; error=str(exc)
   st.session_state.td02_few_result={"stage":2,"scenario":scenario_few,"source":source,"prompt":build_few_shot_prompt(topic),"text":text,"records":records,"error":error,"diagnostics":diagnose_lines(text),"rq_status":diagnose_expected_rqs(text)}
   st.rerun()
 if few:=st.session_state.get("td02_few_result"):
  render_experiment(few,"Résultat du nouvel appel few-shot (TD02)")
  if few["error"]: st.warning("Le few-shot améliore généralement le respect du format, mais cette exécution montre qu'il ne le garantit pas.")
  elif mode=="Cas contrôlés du TD": st.success("Le scénario C réussit globalement. Sélectionnez maintenant D et relancez : les trois RQ resteront valides, mais la ligne d'introduction fera échouer le document complet.")
  else: st.success("Cet appel réel a réussi globalement. Cela ne prouve pas que tous les futurs appels few-shot réussiront.")
if current:=st.session_state.get("td02_few_result"):
 if current["stage"]==2 and current["error"]:
  st.warning("Le few-shot a réduit le risque mais ce cas échoue encore. La réparation conditionnelle est maintenant justifiée.")
  st.subheader("Étape 3 · Réparer seulement l'échec résiduel")
  force_human=False
  if mode=="Cas contrôlés du TD":
   force_human=st.checkbox("Simuler un repair encore invalide pour observer l'escalade humaine",key="force_human")
  if st.button("3 · Corriger avec le LLM puis revalider",icon=":material/looks_3:",type="primary",key="stage3"):
   st.session_state.td02_human_required=None
   st.session_state.td02_repaired=None
   st.session_state.td02_final=None
   if mode=="Cas contrôlés du TD": repaired="réponse encore invalide" if force_human else good
   else:
    try: repaired=repair_with_llm(build_model(settings),current["text"],current["error"])
    except Exception as exc: st.error(str(exc)); repaired=None
   if repaired:
    try:
     records=validate_free_text(repaired)
     st.session_state.td02_repaired={"status":"repaired","text":repaired,"records":records,"repair_attempts":1}
    except Exception as exc:
     st.session_state.td02_human_required={"status":"human_required","repair_attempts":1,"error":str(exc),"text":repaired}
 elif current["stage"]==2 and not current["error"]:
  if st.button("Poursuivre sans repair",icon=":material/check_circle:",type="primary",key="direct_transform"):
   st.session_state.td02_human_required=None
   st.session_state.td02_final=None
   st.session_state.td02_repaired={"status":"accepted","text":current["text"],"records":current["records"],"repair_attempts":0}
if ready:=st.session_state.get("td02_repaired"):
 if ready["status"]=="repaired":
  st.success("Repair réussi : la sortie corrigée respecte maintenant le contrôle regex/Python.")
 else:
  st.success("Sortie conforme : aucun repair LLM n'a été nécessaire.")
 r1,r2=st.columns(2)
 r1.metric("Statut après revalidation",ready["status"].upper())
 r2.metric("Appels de repair",ready["repair_attempts"])
 st.code(ready["text"],language="text")
 st.subheader("Étape 4 · Appliquer Pydantic puis la chaîne LCEL")
 st.caption("Cette étape dépend des TODO 4, 5 et 6. Elle est volontairement séparée du repair du TODO 3.")
 if st.button("4 · Valider le contrat et produire les requêtes",icon=":material/schema:",type="primary",key="stage4"):
  try:
   questions=validate_questions(ready["records"])
   queries=build_question_pipeline().invoke(ready["text"])
   st.session_state.td02_final={"text":ready["text"],"questions":[q.model_dump() for q in questions],"queries":queries}
  except NotImplementedError:
   st.error("Complétez les TODO 4, 5 et 6 avant d'exécuter l'étape Pydantic + LCEL.")
  except Exception as exc:
   st.error("Échec du contrat Pydantic ou de la chaîne LCEL : "+str(exc))
if final:=st.session_state.get("td02_final"):
 st.success("Texte conforme puis transformation déterministe réussie.")
 st.json(final["questions"])
 st.subheader("Stratégie de recherche booléenne produite par la chaîne LCEL")
 st.caption("LCEL orchestre les fonctions. La requête combine les variantes d'un concept par OR et les concepts différents par AND.")
 for engine,query in final["queries"].items():
  with st.expander(engine.upper(),expanded=engine=="scholar"): st.code(query,language="text",wrap_lines=True)
if human:=st.session_state.get("td02_human_required"):
 st.error("Repair refusé après revalidation : le workflow s'arrête.")
 st.json(human)
 st.warning("HITL : un humain doit accepter, corriger ou rejeter la sortie. Aucun second appel automatique n'est lancé.")
st.stop()
