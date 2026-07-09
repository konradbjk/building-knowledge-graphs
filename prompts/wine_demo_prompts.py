import json
from typing import Any


DOCUMENT_METADATA_EXTRACTION_PROMPT = """
# Wine Demo Metadata Extraction
<role>
Extract metadata from one markdown document body about vineyard disease, wine quality, or winemaking.
</role>

<rules>
1. Use only the document body passed in the user message.
2. Stay conservative. If a term is not clearly supported by the document body, leave it out.
3. The result is for metadata indexing, not for final answering.
4. `keywords` should be useful routing phrases for the graph and datastore selection.
5. Do not use datastore names such as `vine_diseases`, `wine_diseases`, or `wine_making` as keywords.
6. Prefer concrete domain phrases such as `gray rot`, `noble rot`, `Bordeaux`, `Mosel`, `central Poland`, `Riesling`, `clarification`, or `beta-glucanase`.
</rules>

Return this exact structure:
{
  "summary": "2-4 sentence summary",
  "regions": ["region or country names"],
  "varieties": ["grape varieties"],
  "diseases": ["diseases or disease-like conditions"],
  "winemaking_steps": ["cellar or processing steps"],
  "quality_effects": ["quality effects, markers, or outcomes"],
  "keywords": ["3-8 routing keywords"]
}
""".strip()


QUESTION_TRIAGE_PROMPT = """
# Wine Demo Question Triage

<role>
Analyze one user question for the wine metadata-routing demo.
</role>

<rules>
1. Extract only the domain terms needed for routing and retrieval.
2. Normalize obvious wine-domain synonyms into the most concrete phrase in the question.
3. `requested_outcome` should capture what the user actually wants: diagnosis, quality interpretation, process advice, or a mixed answer.
4. Do not use datastore names in any field.
5. Prefer direct domain phrases that can map to graph nodes and datastore metadata.
</rules>

<output_structure>
Return this exact structure:
{
  "regions": ["region or country names"],
  "varieties": ["grape varieties"],
  "diseases": ["diseases or disease-like conditions"],
  "winemaking_steps": ["cellar or processing steps"],
  "quality_effects": ["quality effects, markers, or outcomes"],
  "keywords": ["short routing phrases"],
  "requested_outcome": "diagnosis|quality_interpretation|process_advice|mixed"
}
</output_structure>
""".strip()


SQLITE_SQL_TRANSLATION_TEMPLATE = """
# SQLite Datastore Query Translation

You translate one wine question into one SQLite query for one datastore.

The datastore tool provides two explicit blocks below. You must follow them exactly.

SQLITE_SCHEMA:
{schema_sql}

ALLOWED_DATASTORE_VALUES:
{allowed_values_json}

Rules:
1. Use only the tables and columns that appear in `SQLITE_SCHEMA`.
2. Use only literal filter values that appear in `ALLOWED_DATASTORE_VALUES`.
3. Write exactly one `SELECT` query and no explanation in the `sql` field.
4. The query must be safe to execute with positional `?` parameters.
5. The query must return the best top-1 result for this datastore only.
6. Prefer an FTS `MATCH ?` condition plus exact metadata filters when possible.
7. Do not invent joins, tables, columns, filters, or SQL functions not present in the provided schema.
8. Keep the query simple and readable.
9. The `params` list must match the `?` placeholders in order.
10. If the question mentions a region, variety, disease, process, quality effect, or keyword that is not in `ALLOWED_DATASTORE_VALUES`, leave it out rather than guessing.
11. Use `d.country = ?` only with values from `countries`, and `d.region = ?` only with values from `region_labels`.
12. Use `documents_fts MATCH ?` for text retrieval over `title`, `body`, `summary`, and `keyword_blob`.
13. Treat the `*_csv` columns as stored payload only. Do not split them, parse them, or use subqueries on them.
14. When you build the `documents_fts MATCH ?` parameter, use a short boolean expression such as `gray OR rot OR laccase` or quoted phrases joined with `OR`. Do not pass a natural-language sentence or a long space-separated list, because plain spaces act like `AND` in SQLite FTS and often become too strict.
15. If you use FTS, return these columns: `d.document_id`, `d.title`, `d.summary`, `d.source_path`, `d.country`, `d.region`, `snippet(documents_fts, 1, '[', ']', '...', 18) AS snippet`, and optionally `bm25(documents_fts) AS score`.
16. Keep the FTS expression compact, usually 2-6 discriminative terms.

Return this exact structure:
{{
  "sql": "one SQLite SELECT query",
  "params": ["query params in placeholder order"],
  "reason": "one short sentence"
}}
""".strip()


QDRANT_QUERY_TEMPLATE = """
# Qdrant Datastore Query Planning

You translate one wine question into a semantic query plus structured metadata filters for the `wine_making` datastore.

ALLOWED_DATASTORE_VALUES:
{allowed_values_json}

Rules:
1. `query_text` should be a short semantic retrieval string, not a full answer.
2. Use only filter values that appear in `ALLOWED_DATASTORE_VALUES`.
3. Leave a filter list empty instead of guessing.
4. Prefer concrete values taken from the user question.
5. The output is for retrieval only, not for final answering.

Return this exact structure:
{{
  "query_text": "short semantic search text",
  "regions": ["allowed region values"],
  "varieties": ["allowed variety values"],
  "diseases": ["allowed disease values"],
  "winemaking_steps": ["allowed process values"],
  "quality_effects": ["allowed quality effect values"],
  "keywords": ["allowed keyword values"],
  "reason": "one short sentence"
}}
""".strip()


FINAL_SYNTHESIS_PROMPT = """
# Wine Demo Final Answer

Answer the user using only the retrieved text results from the selected datastores.

Rules:
1. Use only the supplied retrieval results.
2. If two datastores were queried, combine both pieces of evidence into one answer.
3. Stay short, concrete, and domain-specific.
4. If the retrieved text is incomplete, say what is missing rather than inventing details.
5. Mention the most relevant disease, quality effect, or cellar step directly.

Return this exact structure:
{
  "answer": "2-4 sentence answer grounded only in the retrieved text"
}
""".strip()


def render_sqlite_sql_prompt(schema_sql: str, allowed_values: dict[str, list[str]]) -> str:
    return SQLITE_SQL_TRANSLATION_TEMPLATE.format(
        schema_sql=schema_sql.strip(),
        allowed_values_json=json.dumps(allowed_values, indent=2, sort_keys=True),
    )


def render_qdrant_query_prompt(allowed_values: dict[str, list[str]]) -> str:
    return QDRANT_QUERY_TEMPLATE.format(
        allowed_values_json=json.dumps(allowed_values, indent=2, sort_keys=True),
    )


def normalize_allowed_values(values: dict[str, list[str]] | dict[str, set[str]]) -> dict[str, list[str]]:
    normalized: dict[str, list[str]] = {}
    for key, raw_values in values.items():
        cleaned = sorted(
            {
                " ".join(str(value).split()).strip()
                for value in raw_values
                if " ".join(str(value).split()).strip()
            }
        )
        normalized[key] = cleaned
    return normalized


def dump_allowed_values(values: dict[str, Any]) -> str:
    return json.dumps(values, indent=2, sort_keys=True)
