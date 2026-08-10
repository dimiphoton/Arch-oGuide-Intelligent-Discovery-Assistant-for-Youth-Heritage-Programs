# Étude de performance — ArchéoGuide

*Généré le 2026-08-10T12:05:01Z (UTC).*

## Objectif

Comparer les stratégies de retrieval et les optimisations avancées (query rewriting, re-ranking) sur un jeu de questions de référence, en mesurant **qualité** (Hit Rate@k, MRR) et **latence**.

## Protocole

- Jeu de référence : `eval/ground_truth.json` (20 questions)
- `top_k` = 5
- Collection Qdrant : `chantiers_archeo`
- Embedding : `text-embedding-3-small`
- LLM : `gpt-4o-mini`
- Pertinence : un chunk est pertinent s'il contient au moins un `expected_keywords` de la question

## 1. Comparaison des modes de retrieval

| Mode | Hit Rate@k | MRR | Latence moyenne | P95 |
|---|---:|---:|---:|---:|
| `vector` | 100.0% | 0.917 | 322 ms | 923 ms |
| `bm25` | 100.0% | 0.821 | 55 ms | 74 ms |
| `hybrid` | 100.0% | 0.902 | 280 ms | 315 ms |

**Meilleur mode (qualité)** : `vector`

## 2. Ablations (rewrite / rerank) sur hybrid

Mesure la qualité des chunks transmis au LLM, sans noter la génération.

| Configuration | Hit Rate@k | MRR | Latence moyenne | P95 |
|---|---:|---:|---:|---:|
| `hybrid (baseline)` | 100.0% | 0.902 | 286 ms | 376 ms |
| `hybrid+rewrite` | 90.0% | 0.817 | 1609 ms | 2314 ms |
| `hybrid+rerank` | 95.0% | 0.900 | 1865 ms | 3276 ms |
| `hybrid+rewrite+rerank` | 95.0% | 0.892 | 3069 ms | 4312 ms |

**Meilleure config avancée** : `hybrid (baseline)`

## 3. Latence end-to-end (pipeline `ask`)

Inclut retrieval + génération de réponse (échantillon de questions).

| Configuration | Questions | Moyenne | P50 | P95 |
|---|---:|---:|---:|---:|
| `e2e` | 5 | 6114 ms | 6134 ms | 7902 ms |
| `e2e+rewrite+rerank` | 5 | 7745 ms | 7087 ms | 9004 ms |

## Conclusions

- Le mode `vector` offre le meilleur couple Hit Rate / MRR (100.0% / 0.917).
- Rewrite + rerank n'améliorent pas le Hit Rate ici (-5.0%) ; utile surtout pour le ranking (MRR) ou la qualité perçue des réponses.
- La config recommandée en production reste celle du meilleur score qualité/latence observé (voir tableaux).

---

*Reproduire : `python scripts/run_performance_study.py`*
