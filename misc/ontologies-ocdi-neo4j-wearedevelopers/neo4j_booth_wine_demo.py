# %% [markdown]
# # Neo4j Booth Wine Demo
# 
# Neo4j Aura indexes aggregated datastore metadata and datastore overlap.
# Each datastore tool owns its own retrieval logic.

# %% [markdown]
# ## Flow
# 
# 1. inspect the curated corpus
# 2. run one live metadata extraction
# 3. build SQLite datastores for `vine_diseases` and `wine_diseases`
# 4. show the optional Qdrant path for `wine_making`
# 5. create the aggregated Neo4j graph
# 6. run manual Cypher to see what information is where
# 7. run the LangGraph workflow over the three live questions

# %%
import asyncio
import json
import os
import re
import runpy
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Literal, TypedDict

import cohere
import frontmatter
import pandas as pd
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langgraph.graph import END, START, StateGraph
from neo4j import GraphDatabase, RoutingControl
from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from qdrant_client import QdrantClient, models

# %%
load_dotenv(dotenv_path=Path('.env'), override=False)

PROJECT_ROOT = Path.cwd()
DATA_ROOT = PROJECT_ROOT / 'data' / 'winde_demo'
PROCESSED_DIR = PROJECT_ROOT / 'processed' / 'winde_demo'
JSONL_PATH = PROCESSED_DIR / 'metadata_extractions.jsonl'
CHUNK_JSONL_PATH = PROCESSED_DIR / 'wine_making_chunks.jsonl'
SQLITE_DIR = PROCESSED_DIR / 'sqlite'

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
SQLITE_DIR.mkdir(parents=True, exist_ok=True)

AZURE_OPENAI_DEPLOYMENT = os.getenv('WINE_DEMO_MODEL') or os.getenv('AZURE_OPENAI_DEPLOYMENT') or '<azure-openai-deployment>'
COHERE_EMBED_MODEL = os.getenv('COHERE_EMBED_MODEL', 'embed-v4.0')
DEMO_ID = os.getenv('WINE_DEMO_ID', 'neo4j-booth-wine-demo')

NEO4J_USERNAME = os.getenv('NEO4J_USERNAME', '<neo4j-username>')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD', '<password>')
NEO4J_INSTANCE_ID = os.getenv('NEO4J_INSTANCE_ID') or os.getenv('NEO4J_AURA_INSTANCE_ID')
NEO4J_URI = os.getenv('NEO4J_URI') or (
    f'neo4j+s://{NEO4J_INSTANCE_ID}.databases.neo4j.io'
    if NEO4J_INSTANCE_ID
    else 'neo4j+s://<aura-instance-id>.databases.neo4j.io'
)

QDRANT_URL = os.getenv('QDRANT_URL', 'http://localhost:6333')
QDRANT_API_KEY = os.getenv('QDRANT_API_KEY')
QDRANT_COLLECTION = os.getenv('WINE_DEMO_QDRANT_COLLECTION', 'wine_making_chunks')

REPOSITORY_ORDER = ['vine_diseases', 'wine_diseases', 'wine_making']
STORE_DESCRIPTIONS = {
    'vine_diseases': 'Vineyard disease pressure, cultivar susceptibility, and region-level growing risk.',
    'wine_diseases': 'How disease or botrytised fruit changes must and wine quality.',
    'wine_making': 'Cellar operations, clarification, filtration, enzymes, and process handling.',
}
TERM_FIELDS = [
    ('regions', 'Region'),
    ('varieties', 'Variety'),
    ('diseases', 'Disease'),
    ('winemaking_steps', 'Process'),
    ('quality_effects', 'QualityEffect'),
    ('keywords', 'Keyword'),
]

print(f'Data root: {DATA_ROOT}')
print(f'Azure deployment: {AZURE_OPENAI_DEPLOYMENT}')
print(f'Cohere embedding model: {COHERE_EMBED_MODEL}')
print(f'Neo4j URI: {NEO4J_URI}')
print(f'Qdrant collection: {QDRANT_COLLECTION}')

# %% [markdown]
# ## Inspect The Curated Corpus
# The corpus already contains long topical briefs with `metadata:` frontmatter.

# %%
CORPUS_PATHS = sorted(DATA_ROOT.rglob('*.md'))
if not CORPUS_PATHS:
    raise RuntimeError(f'No markdown files found under {DATA_ROOT}')

print(f'Total markdown files: {len(CORPUS_PATHS)}')
pd.Series([path.parent.name for path in CORPUS_PATHS]).value_counts().rename_axis('repository').to_frame('documents')

# %%
sample_path = CORPUS_PATHS[0]
sample_post = frontmatter.load(sample_path)

print(sample_path.relative_to(PROJECT_ROOT))
print(sample_post.metadata)
print()
print(sample_post.content[:1200])

# %% [markdown]
# ## Models
# `pydantic-ai` is used for extraction, triage, SQL translation, Qdrant query planning, and final synthesis.

# %%
def normalize_text(text: str) -> str:
    return re.sub(r'\s+', ' ', text or '').strip().lower()


def clean_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        values = [value]
    else:
        values = list(value)

    cleaned: list[str] = []
    seen: set[str] = set()
    for item in values:
        normalized = ' '.join(str(item).split()).strip()
        key = normalized.casefold()
        if not normalized or key in seen:
            continue
        seen.add(key)
        cleaned.append(normalized)
    return cleaned


class MetadataExtraction(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    summary: str = Field(description='A concise 2-4 sentence summary.')
    regions: list[str] = Field(default_factory=list)
    varieties: list[str] = Field(default_factory=list)
    diseases: list[str] = Field(default_factory=list)
    winemaking_steps: list[str] = Field(default_factory=list)
    quality_effects: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)

    @field_validator(
        'regions',
        'varieties',
        'diseases',
        'winemaking_steps',
        'quality_effects',
        'keywords',
        mode='before',
    )
    @classmethod
    def ensure_list(cls, value: Any) -> list[str]:
        return clean_list(value)


class QuestionTriage(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    regions: list[str] = Field(default_factory=list)
    varieties: list[str] = Field(default_factory=list)
    diseases: list[str] = Field(default_factory=list)
    winemaking_steps: list[str] = Field(default_factory=list)
    quality_effects: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    requested_outcome: Literal['diagnosis', 'quality_interpretation', 'process_advice', 'mixed']

    @field_validator(
        'regions',
        'varieties',
        'diseases',
        'winemaking_steps',
        'quality_effects',
        'keywords',
        mode='before',
    )
    @classmethod
    def ensure_list(cls, value: Any) -> list[str]:
        return clean_list(value)


class SqliteQueryPlan(BaseModel):
    sql: str
    params: list[str] = Field(default_factory=list)
    reason: str


class QdrantQueryPlan(BaseModel):
    query_text: str
    regions: list[str] = Field(default_factory=list)
    varieties: list[str] = Field(default_factory=list)
    diseases: list[str] = Field(default_factory=list)
    winemaking_steps: list[str] = Field(default_factory=list)
    quality_effects: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    reason: str

    @field_validator(
        'regions',
        'varieties',
        'diseases',
        'winemaking_steps',
        'quality_effects',
        'keywords',
        mode='before',
    )
    @classmethod
    def ensure_list(cls, value: Any) -> list[str]:
        return clean_list(value)


class FinalAnswer(BaseModel):
    answer: str

# %% [markdown]
# ## Load Prompts
# The notebook only uses `prompts/wine_demo_prompts.py`.

# %%
PROMPTS = runpy.run_path(str(PROJECT_ROOT / 'prompts' / 'wine_demo_prompts.py'))

DOCUMENT_METADATA_EXTRACTION_PROMPT = PROMPTS['DOCUMENT_METADATA_EXTRACTION_PROMPT']
QUESTION_TRIAGE_PROMPT = PROMPTS['QUESTION_TRIAGE_PROMPT']
FINAL_SYNTHESIS_PROMPT = PROMPTS['FINAL_SYNTHESIS_PROMPT']
render_sqlite_sql_prompt = PROMPTS['render_sqlite_sql_prompt']
render_qdrant_query_prompt = PROMPTS['render_qdrant_query_prompt']
normalize_allowed_values = PROMPTS['normalize_allowed_values']

print(PROJECT_ROOT / 'prompts' / 'wine_demo_prompts.py')

# %%
def normalize_azure_openai_base_url(endpoint: str) -> str:
    normalized = endpoint.rstrip('/')
    if normalized.endswith('/openai/v1'):
        return normalized + '/'
    if normalized.endswith('/openai'):
        return normalized + '/v1/'
    if '.openai.azure.com' in normalized:
        return normalized + '/openai/v1/'
    return normalized + '/'


def build_chat_model(model_name: str) -> OpenAIChatModel:
    api_key = os.getenv('AZURE_OPENAI_API_KEY')
    azure_endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
    deployment = model_name or AZURE_OPENAI_DEPLOYMENT
    missing = [
        name
        for name, value in [
            ('AZURE_OPENAI_API_KEY', api_key),
            ('AZURE_OPENAI_ENDPOINT', azure_endpoint),
            ('AZURE_OPENAI_DEPLOYMENT', deployment if deployment != '<azure-openai-deployment>' else ''),
        ]
        if not value
    ]
    if missing:
        raise ValueError(
            'Set the Azure OpenAI chat env vars before running model-backed notebook cells: '
            + ', '.join(missing)
        )

    client = AsyncOpenAI(
        base_url=normalize_azure_openai_base_url(azure_endpoint),
        api_key=api_key,
    )
    return OpenAIChatModel(deployment, provider=OpenAIProvider(openai_client=client))

# %% [markdown]
# ## Shared Agents
# Build the reusable extraction, triage, and synthesis agents once so later cells can call them directly.

# %%
chat_model = build_chat_model(AZURE_OPENAI_DEPLOYMENT)
metadata_agent = Agent(
    chat_model,
    instructions=DOCUMENT_METADATA_EXTRACTION_PROMPT,
    output_type=MetadataExtraction,
)
triage_agent = Agent(
    chat_model,
    instructions=QUESTION_TRIAGE_PROMPT,
    output_type=QuestionTriage,
)
final_answer_agent = Agent(
    chat_model,
    instructions=FINAL_SYNTHESIS_PROMPT,
    output_type=FinalAnswer,
)

# %% [markdown]
# ## Run One Live Metadata Extraction
# This is the booth-safe LLM path: one document, one extraction, visible output.

# %%
one_extraction = await metadata_agent.run(
    f"""
    Extract metadata from this markdown document body.

    <document_body>
    {sample_post.content}
    </document_body>
    """.strip()
)

one_extraction.output

# %% [markdown]
# ## Load Documents And Aggregate Metadata
# The graph is built from aggregated datastore metadata, not from document nodes.

# %%
def build_keyword_blob(document: dict[str, Any]) -> str:
    metadata = document['metadata']
    pieces = [
        document['title'],
        document['country'],
        document['region'],
        metadata['summary'],
    ]
    for field_name, _ in TERM_FIELDS:
        pieces.extend(metadata[field_name])
    return ' | '.join(piece for piece in pieces if piece)


def load_demo_documents(data_root: Path) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for path in sorted(data_root.rglob('*.md')):
        post = frontmatter.load(path)
        metadata = MetadataExtraction.model_validate(post.metadata['metadata']).model_dump(mode='json')
        metadata['regions'] = clean_list(
            [
                post.metadata.get('country', ''),
                post.metadata.get('region', ''),
                *metadata['regions'],
            ]
        )
        document = {
            'document_id': str(path.relative_to(PROJECT_ROOT)),
            'title': post.metadata['title'],
            'repository': post.metadata['repository'],
            'country': post.metadata.get('country', ''),
            'region': post.metadata.get('region', ''),
            'source': post.metadata.get('source', ''),
            'source_urls': list(post.metadata.get('source_urls', [])),
            'source_path': str(path.relative_to(PROJECT_ROOT)),
            'content': post.content.strip(),
            'metadata': metadata,
        }
        document['keyword_blob'] = build_keyword_blob(document)
        documents.append(document)
    return documents


def build_repository_allowed_values(documents: list[dict[str, Any]]) -> dict[str, dict[str, list[str]]]:
    values: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for document in documents:
        repository = document['repository']
        if document['country']:
            values[repository]['countries'].add(document['country'])
        if document['region']:
            values[repository]['region_labels'].add(document['region'])
        values[repository]['sources'].add(document['source'])
        for field_name, _ in TERM_FIELDS:
            values[repository][field_name].update(document['metadata'][field_name])
    return {
        repository: normalize_allowed_values(repository_values)
        for repository, repository_values in values.items()
    }


def build_coverage_rows(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counter: Counter[tuple[str, str, str, str]] = Counter()
    for document in documents:
        repository = document['repository']
        for field_name, label in TERM_FIELDS:
            for value in document['metadata'][field_name]:
                counter[(repository, label, value, normalize_text(value))] += 1

    rows = [
        {
            'datastore': repository,
            'term_type': label,
            'term': term,
            'term_normalized': term_normalized,
            'count': count,
        }
        for (repository, label, term, term_normalized), count in counter.items()
    ]
    return sorted(rows, key=lambda row: (row['datastore'], row['term_type'], row['term']))


def build_overlap_rows(coverage_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_repository: dict[str, dict[str, dict[str, str]]] = defaultdict(lambda: defaultdict(dict))
    for row in coverage_rows:
        by_repository[row['datastore']][row['term_type']][row['term_normalized']] = row['term']

    overlaps: list[dict[str, Any]] = []
    for index, left in enumerate(REPOSITORY_ORDER):
        for right in REPOSITORY_ORDER[index + 1:]:
            shared_terms: list[str] = []
            shared_types: list[str] = []
            left_terms = by_repository[left]
            right_terms = by_repository[right]
            for term_type in sorted(set(left_terms) | set(right_terms)):
                shared_keys = sorted(set(left_terms[term_type]) & set(right_terms[term_type]))
                if not shared_keys:
                    continue
                shared_types.append(term_type)
                shared_terms.extend(left_terms[term_type][key] for key in shared_keys)
            if shared_terms:
                overlaps.append(
                    {
                        'left_datastore': left,
                        'right_datastore': right,
                        'shared_terms': shared_terms,
                        'shared_types': shared_types,
                        'score': len(shared_terms),
                    }
                )
    return overlaps


def triage_terms(triage: QuestionTriage) -> list[str]:
    return clean_list(
        triage.regions
        + triage.varieties
        + triage.diseases
        + triage.winemaking_steps
        + triage.quality_effects
        + triage.keywords
    )

# %%
documents = load_demo_documents(DATA_ROOT)
REPOSITORY_ALLOWED_VALUES = build_repository_allowed_values(documents)
coverage_rows = build_coverage_rows(documents)
overlap_rows = build_overlap_rows(coverage_rows)

print(f'Loaded {len(documents)} documents')
pd.DataFrame(coverage_rows).head(12)

# %%
pd.DataFrame(overlap_rows)

# %% [markdown]
# ## Batch Extraction Checkpoint
# The frontmatter already contains metadata.
# This optional rebuild path only reruns extraction if you want to refresh the JSONL checkpoints offline.

# %%
extraction_records: list[dict[str, Any]] = []

with JSONL_PATH.open('w', encoding='utf-8') as jsonl_file:
    for document in documents:
        result = await metadata_agent.run(
            f"""
            Extract metadata from this markdown document body.

            <document_body>
            {document['content']}
            </document_body>
            """.strip()
        )
        record = {
            'document_id': document['document_id'],
            'repository': document['repository'],
            'source_path': document['source_path'],
            'metadata': result.output.model_dump(mode='json'),
        }
        jsonl_file.write(json.dumps(record, ensure_ascii=False) + '\n')
        jsonl_file.flush()
        extraction_records.append(record)

print(f'Wrote {len(extraction_records)} checkpoint records to {JSONL_PATH}')

# %% [markdown]
# ## SQLite Datastore 1: `vine_diseases`
# Seed the vineyard disease store directly from the curated markdown and stored metadata.
# The list-like metadata fields are kept as readable `*_csv` payload columns because SQLite never queries inside them.

# %%
VINE_DISEASES_DB_PATH = SQLITE_DIR / 'vine_diseases.db'
vine_diseases_documents = [document for document in documents if document['repository'] == 'vine_diseases']

VINE_DISEASES_SCHEMA_SQL = """
CREATE TABLE documents (
  rowid INTEGER PRIMARY KEY AUTOINCREMENT,
  document_id TEXT UNIQUE NOT NULL,
  title TEXT NOT NULL,
  repository TEXT NOT NULL,
  country TEXT,
  region TEXT,
  source TEXT,
  source_path TEXT,
  summary TEXT,
  body TEXT,
  regions_csv TEXT,
  varieties_csv TEXT,
  diseases_csv TEXT,
  winemaking_steps_csv TEXT,
  quality_effects_csv TEXT,
  keywords_csv TEXT,
  keyword_blob TEXT
);

CREATE VIRTUAL TABLE documents_fts USING fts5(
  title,
  body,
  summary,
  keyword_blob,
  content='documents',
  content_rowid='rowid'
);
""".strip()

vine_diseases_seed_db = sqlite3.connect(VINE_DISEASES_DB_PATH)
vine_diseases_seed_db.executescript(
    """
    PRAGMA foreign_keys = ON;
    DROP TABLE IF EXISTS documents_fts;
    DROP TABLE IF EXISTS documents;
    """
)
vine_diseases_seed_db.executescript(VINE_DISEASES_SCHEMA_SQL)

for document in vine_diseases_documents:
    metadata = document['metadata']
    cursor = vine_diseases_seed_db.execute(
        """
        INSERT INTO documents (
            document_id,
            title,
            repository,
            country,
            region,
            source,
            source_path,
            summary,
            body,
            regions_csv,
            varieties_csv,
            diseases_csv,
            winemaking_steps_csv,
            quality_effects_csv,
            keywords_csv,
            keyword_blob
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            document['document_id'],
            document['title'],
            document['repository'],
            document['country'],
            document['region'],
            document['source'],
            document['source_path'],
            metadata['summary'],
            document['content'],
            ', '.join(metadata['regions']),
            ', '.join(metadata['varieties']),
            ', '.join(metadata['diseases']),
            ', '.join(metadata['winemaking_steps']),
            ', '.join(metadata['quality_effects']),
            ', '.join(metadata['keywords']),
            document['keyword_blob'],
        ),
    )
    rowid = cursor.lastrowid
    vine_diseases_seed_db.execute(
        'INSERT INTO documents_fts(rowid, title, body, summary, keyword_blob) VALUES (?, ?, ?, ?, ?)',
        (
            rowid,
            document['title'],
            document['content'],
            metadata['summary'],
            document['keyword_blob'],
        ),
    )

vine_diseases_seed_db.commit()
vine_diseases_seed_db.close()

{
    'db_path': str(VINE_DISEASES_DB_PATH),
    'documents_seeded': len(vine_diseases_documents),
}

# %% [markdown]
# ## SQLite Datastore 2: `wine_diseases`
# Seed the wine quality store separately so the second datastore is visible as its own organism.
# The list-like metadata fields stay as readable `*_csv` payload columns here as well.

# %%
WINE_DISEASES_DB_PATH = SQLITE_DIR / 'wine_diseases.db'
wine_diseases_documents = [document for document in documents if document['repository'] == 'wine_diseases']

WINE_DISEASES_SCHEMA_SQL = """
CREATE TABLE documents (
  rowid INTEGER PRIMARY KEY AUTOINCREMENT,
  document_id TEXT UNIQUE NOT NULL,
  title TEXT NOT NULL,
  repository TEXT NOT NULL,
  country TEXT,
  region TEXT,
  source TEXT,
  source_path TEXT,
  summary TEXT,
  body TEXT,
  regions_csv TEXT,
  varieties_csv TEXT,
  diseases_csv TEXT,
  winemaking_steps_csv TEXT,
  quality_effects_csv TEXT,
  keywords_csv TEXT,
  keyword_blob TEXT
);

CREATE VIRTUAL TABLE documents_fts USING fts5(
  title,
  body,
  summary,
  keyword_blob,
  content='documents',
  content_rowid='rowid'
);
""".strip()

wine_diseases_seed_db = sqlite3.connect(WINE_DISEASES_DB_PATH)
wine_diseases_seed_db.executescript(
    """
    PRAGMA foreign_keys = ON;
    DROP TABLE IF EXISTS documents_fts;
    DROP TABLE IF EXISTS documents;
    """
)
wine_diseases_seed_db.executescript(WINE_DISEASES_SCHEMA_SQL)

for document in wine_diseases_documents:
    metadata = document['metadata']
    cursor = wine_diseases_seed_db.execute(
        """
        INSERT INTO documents (
            document_id,
            title,
            repository,
            country,
            region,
            source,
            source_path,
            summary,
            body,
            regions_csv,
            varieties_csv,
            diseases_csv,
            winemaking_steps_csv,
            quality_effects_csv,
            keywords_csv,
            keyword_blob
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            document['document_id'],
            document['title'],
            document['repository'],
            document['country'],
            document['region'],
            document['source'],
            document['source_path'],
            metadata['summary'],
            document['content'],
            ', '.join(metadata['regions']),
            ', '.join(metadata['varieties']),
            ', '.join(metadata['diseases']),
            ', '.join(metadata['winemaking_steps']),
            ', '.join(metadata['quality_effects']),
            ', '.join(metadata['keywords']),
            document['keyword_blob'],
        ),
    )
    rowid = cursor.lastrowid
    wine_diseases_seed_db.execute(
        'INSERT INTO documents_fts(rowid, title, body, summary, keyword_blob) VALUES (?, ?, ?, ?, ?)',
        (
            rowid,
            document['title'],
            document['content'],
            metadata['summary'],
            document['keyword_blob'],
        ),
    )

wine_diseases_seed_db.commit()
wine_diseases_seed_db.close()

{
    'db_path': str(WINE_DISEASES_DB_PATH),
    'documents_seeded': len(wine_diseases_documents),
}

# %% [markdown]
# ## Load Existing SQLite Datastores
# Open each SQLite file separately so the rest of the notebook can start from the existing stores.

# %%
vine_diseases_db = sqlite3.connect(VINE_DISEASES_DB_PATH)
vine_diseases_db.row_factory = sqlite3.Row
vine_diseases_schema_rows = vine_diseases_db.execute(
    """
    SELECT sql
    FROM sqlite_master
    WHERE type IN ('table', 'view')
      AND name NOT LIKE 'sqlite_%'
    ORDER BY name
    """
).fetchall()
vine_diseases_schema_sql = '\n\n'.join(row['sql'] for row in vine_diseases_schema_rows if row['sql'])

{
    'db_path': str(VINE_DISEASES_DB_PATH),
    'tables': [row['name'] for row in vine_diseases_db.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'view') ORDER BY name").fetchall()],
    'documents': vine_diseases_db.execute('SELECT COUNT(*) AS count FROM documents').fetchone()['count'],
}

# %%
wine_diseases_db = sqlite3.connect(WINE_DISEASES_DB_PATH)
wine_diseases_db.row_factory = sqlite3.Row
wine_diseases_schema_rows = wine_diseases_db.execute(
    """
    SELECT sql
    FROM sqlite_master
    WHERE type IN ('table', 'view')
      AND name NOT LIKE 'sqlite_%'
    ORDER BY name
    """
).fetchall()
wine_diseases_schema_sql = '\n\n'.join(row['sql'] for row in wine_diseases_schema_rows if row['sql'])

{
    'db_path': str(WINE_DISEASES_DB_PATH),
    'tables': [row['name'] for row in wine_diseases_db.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'view') ORDER BY name").fetchall()],
    'documents': wine_diseases_db.execute('SELECT COUNT(*) AS count FROM documents').fetchone()['count'],
}

# %%
vine_diseases_demo_row = dict(
    vine_diseases_db.execute(
        """
        SELECT
          d.document_id,
          d.title,
          d.region,
          d.summary,
          d.source_path,
          snippet(documents_fts, 1, '[', ']', '...', 18) AS snippet,
          bm25(documents_fts) AS score
        FROM documents_fts
        JOIN documents d ON d.rowid = documents_fts.rowid
        WHERE documents_fts MATCH ?
          AND d.country = ?
        ORDER BY score
        LIMIT 1
        """,
        ('central OR Poland OR cultivars OR fungal', 'Poland'),
    ).fetchone()
)
vine_diseases_demo_row

# %%
wine_diseases_demo_row = dict(
    wine_diseases_db.execute(
        """
        SELECT
          d.document_id,
          d.title,
          d.region,
          d.summary,
          d.source_path,
          snippet(documents_fts, 1, '[', ']', '...', 18) AS snippet,
          bm25(documents_fts) AS score
        FROM documents_fts
        JOIN documents d ON d.rowid = documents_fts.rowid
        WHERE documents_fts MATCH ?
          AND d.country = ?
        ORDER BY score
        LIMIT 1
        """,
        ('gray OR rot OR laccase OR Bordeaux', 'France'),
    ).fetchone()
)
wine_diseases_demo_row

# %%
def validate_sqlite_select(sql: str) -> None:
    normalized = sql.strip().lower()
    if not normalized.startswith('select'):
        raise ValueError(f'SQLite tool must emit a SELECT query, got: {sql}')
    forbidden_tokens = [' insert ', ' update ', ' delete ', ' drop ', ' alter ', ' pragma ', ' attach ', ' detach ']
    padded = f' {normalized} '
    for token in forbidden_tokens:
        if token in padded:
            raise ValueError(f'Forbidden SQL token in generated query: {token.strip()}')


async def sqlite_tool(question: str, triage: QuestionTriage, repository: str) -> dict[str, Any]:
    if repository == 'vine_diseases':
        db_path = VINE_DISEASES_DB_PATH
        schema_sql = vine_diseases_schema_sql
    elif repository == 'wine_diseases':
        db_path = WINE_DISEASES_DB_PATH
        schema_sql = wine_diseases_schema_sql
    else:
        raise ValueError(f'Unknown SQLite datastore: {repository}')

    allowed_values = REPOSITORY_ALLOWED_VALUES[repository]
    prompt = render_sqlite_sql_prompt(schema_sql, allowed_values)
    agent = Agent(
        build_chat_model(AZURE_OPENAI_DEPLOYMENT),
        instructions=prompt,
        output_type=SqliteQueryPlan,
    )
    request = f"""
    User question:
    {question}

    Normalized triage:
    {triage.model_dump_json(indent=2)}

    Datastore:
    {repository}
    """.strip()
    plan = (await agent.run(request)).output
    validate_sqlite_select(plan.sql)

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    rows = [dict(row) for row in connection.execute(plan.sql, plan.params).fetchall()]
    if not rows:
        fallback_terms = clean_list(
            triage.diseases
            + triage.varieties
            + triage.winemaking_steps
            + triage.quality_effects
            + triage.keywords
        )
        fallback_match = ' OR '.join(
            f'"{term}"' if ' ' in term else term
            for term in fallback_terms[:6]
        )
        fallback_sql = """
        SELECT
          d.document_id,
          d.title,
          d.summary,
          d.source_path,
          d.country,
          d.region,
          snippet(documents_fts, 1, '[', ']', '...', 18) AS snippet,
          bm25(documents_fts) AS score
        FROM documents_fts
        JOIN documents d ON d.rowid = documents_fts.rowid
        WHERE documents_fts MATCH ?
        """.strip()
        fallback_params: list[str] = [fallback_match or question]
        country_values = REPOSITORY_ALLOWED_VALUES[repository].get('countries', [])
        region_values = REPOSITORY_ALLOWED_VALUES[repository].get('region_labels', [])
        for region in triage.regions:
            if region in country_values:
                fallback_sql += '\n  AND d.country = ?'
                fallback_params.append(region)
                break
            if region in region_values:
                fallback_sql += '\n  AND d.region = ?'
                fallback_params.append(region)
                break
        fallback_sql += '\nORDER BY score\nLIMIT 1'
        rows = [dict(row) for row in connection.execute(fallback_sql, fallback_params).fetchall()]
    connection.close()
    top_result = rows[0] if rows else None
    if top_result:
        parts = [
            f"Title: {top_result.get('title', '')}",
            f"Region: {top_result.get('region', '')}",
            f"Source path: {top_result.get('source_path', '')}",
            f"Summary: {top_result.get('summary', '')}",
        ]
        if top_result.get('snippet'):
            parts.append(f"Snippet: {top_result['snippet']}")
        text = '\n'.join(part for part in parts if part and not part.endswith(': '))
    else:
        text = 'No result.'
    return {
        'datastore': repository,
        'query_plan': plan.model_dump(mode='json'),
        'top_result': top_result,
        'text': text,
    }

# %% [markdown]
# ## Qdrant Path For `wine_making`
# Use a local Qdrant running in Docker, chunk the cellar-process documents, extract chunk metadata, then load the existing collection again for retrieval.
# The chunking, extraction, and upsert cells are precompute cells; the live booth path can jump straight to loading the existing collection.

# %% [markdown]
# ### Chunk `wine_making` Documents
# Split the text with LangChain's `RecursiveCharacterTextSplitter` and keep parent-document plus chunk-number metadata.

# %%
wine_making_documents = [document for document in documents if document['repository'] == 'wine_making']
wine_making_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
wine_making_chunks: list[dict[str, Any]] = []

for document in wine_making_documents:
    chunk_texts = wine_making_splitter.split_text(document['content'])
    for chunk_number, chunk_text in enumerate(chunk_texts, start=1):
        wine_making_chunks.append(
            {
                'chunk_id': f"{document['document_id']}::chunk::{chunk_number}",
                'document_id': document['document_id'],
                'chunk_number': chunk_number,
                'repository': document['repository'],
                'title': document['title'],
                'text': chunk_text,
                'metadata': {
                    **document['metadata'],
                    'country': document['country'],
                    'region_label': document['region'],
                    'source': document['source'],
                    'source_path': document['source_path'],
                    'parent_document_id': document['document_id'],
                    'parent_title': document['title'],
                    'chunk_number': chunk_number,
                },
            }
        )

pd.DataFrame(
    {
        'chunk_id': chunk['chunk_id'],
        'parent_document_id': chunk['document_id'],
        'chunk_number': chunk['chunk_number'],
        'title': chunk['title'],
        'length': len(chunk['text']),
    }
    for chunk in wine_making_chunks[:10]
)

# %% [markdown]
# ### Extract Metadata For The Chunks
# Each chunk gets its own metadata extraction while still keeping the parent-document and chunk-number trace.

# %%
enriched_wine_making_chunks: list[dict[str, Any]] = []

with CHUNK_JSONL_PATH.open('w', encoding='utf-8') as jsonl_file:
    for chunk in wine_making_chunks:
        result = await metadata_agent.run(
            f"""
            Extract metadata from this markdown document body.

            <document_body>
            {chunk['text']}
            </document_body>
            """.strip()
        )
        enriched = {
            **chunk,
            'metadata': {
                **chunk['metadata'],
                **result.output.model_dump(mode='json'),
            },
        }
        jsonl_file.write(json.dumps(enriched, ensure_ascii=False) + '\n')
        jsonl_file.flush()
        enriched_wine_making_chunks.append(enriched)

print(f'Wrote {len(enriched_wine_making_chunks)} chunk records to {CHUNK_JSONL_PATH}')

# %% [markdown]
# ### Seed The Local Qdrant Collection
# This is the indexing pass against the local Docker-backed Qdrant.

# %%
COHERE_API_KEY = os.getenv('COHERE_API_KEY')
if not COHERE_API_KEY:
    raise ValueError('Set COHERE_API_KEY before running the Qdrant seed cell.')

cohere_client = cohere.ClientV2(api_key=COHERE_API_KEY)

try:
    qdrant_seed_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY) if QDRANT_API_KEY else QdrantClient(url=QDRANT_URL)
    existing_qdrant_collections = {collection.name for collection in qdrant_seed_client.get_collections().collections}
except Exception as exc:
    raise RuntimeError(
        f'Could not connect to Qdrant at {QDRANT_URL}. Start the local service with `docker compose up qdrant` before running the Qdrant cells.'
    ) from exc

wine_making_vectors = cohere_client.embed(
    model=COHERE_EMBED_MODEL,
    input_type='search_document',
    texts=[chunk['text'] for chunk in enriched_wine_making_chunks],
    embedding_types=['float'],
).embeddings.float
qdrant_point_ids = list(range(1, len(enriched_wine_making_chunks) + 1))

if QDRANT_COLLECTION not in existing_qdrant_collections:
    qdrant_seed_client.create_collection(
        collection_name=QDRANT_COLLECTION,
        vectors_config=models.VectorParams(size=len(wine_making_vectors[0]), distance=models.Distance.COSINE),
    )

qdrant_seed_client.upsert(
    collection_name=QDRANT_COLLECTION,
    wait=True,
    points=models.Batch(
        ids=qdrant_point_ids,
        vectors=wine_making_vectors,
        payloads=[
            {
                'chunk_id': chunk['chunk_id'],
                'text': chunk['text'],
                'title': chunk['title'],
                'document_id': chunk['document_id'],
                'chunk_number': chunk['chunk_number'],
                'metadata': chunk['metadata'],
            }
            for chunk in enriched_wine_making_chunks
        ],
    ),
)
qdrant_seed_client.get_collection(QDRANT_COLLECTION)

# %% [markdown]
# ### Load The Existing Qdrant Collection
# Open a fresh client against the same collection so retrieval can start from the already-indexed state.
# If the collection was already built earlier, this is the entry point for the live demo.

# %%
try:
    qdrant_query_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY) if QDRANT_API_KEY else QdrantClient(url=QDRANT_URL)
    qdrant_query_client.get_collection(QDRANT_COLLECTION)
except Exception as exc:
    raise RuntimeError(
        f'Could not load Qdrant collection `{QDRANT_COLLECTION}` at {QDRANT_URL}. Seed the collection first and make sure the local Qdrant service is running.'
    ) from exc

# %%
async def qdrant_tool(question: str, triage: QuestionTriage) -> dict[str, Any]:
    if 'qdrant_query_client' not in globals():
        raise RuntimeError('Run the existing Qdrant collection load cell before using the wine_making retrieval tool.')

    prompt = render_qdrant_query_prompt(REPOSITORY_ALLOWED_VALUES['wine_making'])
    agent = Agent(
        build_chat_model(AZURE_OPENAI_DEPLOYMENT),
        instructions=prompt,
        output_type=QdrantQueryPlan,
    )
    request = f"""
    User question:
    {question}

    Normalized triage:
    {triage.model_dump_json(indent=2)}
    """.strip()
    plan = (await agent.run(request)).output

    cohere_client = cohere.ClientV2(api_key=os.environ['COHERE_API_KEY'])
    query_vector = cohere_client.embed(
        model=COHERE_EMBED_MODEL,
        input_type='search_query',
        texts=[plan.query_text],
        embedding_types=['float'],
    ).embeddings.float[0]

    must_conditions: list[models.Condition] = []
    for field_name in ['regions', 'varieties', 'diseases', 'winemaking_steps', 'quality_effects', 'keywords']:
        values = getattr(plan, field_name)
        if not values:
            continue
        must_conditions.append(
            models.FieldCondition(
                key=f'metadata.{field_name}',
                match=models.MatchAny(any=values),
            )
        )
    query_filter = models.Filter(must=must_conditions) if must_conditions else None

    try:
        result = qdrant_query_client.query_points(
            collection_name=QDRANT_COLLECTION,
            query=query_vector,
            limit=1,
            with_payload=True,
            query_filter=query_filter,
        )
    except Exception as exc:
        raise RuntimeError(
            f'Qdrant query failed against `{QDRANT_COLLECTION}` at {QDRANT_URL}. Check that the collection exists and the local service is running.'
        ) from exc
    top_point = result.points[0] if result.points else None
    if top_point is not None:
        payload = top_point.payload or {}
        metadata = payload.get('metadata', {})
        text = '\n'.join(
            part
            for part in [
                f"Title: {payload.get('title', '')}",
                f"Chunk number: {payload.get('chunk_number', '')}",
                f"Source path: {metadata.get('source_path', '')}",
                f"Text: {payload.get('text', '')}",
            ]
            if part and not part.endswith(': ')
        )
    else:
        text = 'No result.'
    return {
        'datastore': 'wine_making',
        'query_plan': plan.model_dump(mode='json'),
        'top_result': top_point,
        'text': text,
    }

# %% [markdown]
# ## Neo4j Aura Graph
# Neo4j stores only aggregated datastore coverage and datastore overlap.

# %%
def get_neo4j_driver():
    if any(token in NEO4J_URI for token in ['<instance>', '<instance-id>', '<aura-instance-id>']) or any(
        token in value
        for token, value in [
            ('<neo4j-username>', NEO4J_USERNAME),
            ('<password>', NEO4J_PASSWORD),
        ]
    ):
        raise ValueError(
            'Set NEO4J_URI (or NEO4J_INSTANCE_ID), NEO4J_USERNAME, and NEO4J_PASSWORD before running the Neo4j Aura cells.'
        )
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))


def require_driver():
    global DRIVER
    if 'DRIVER' not in globals() or DRIVER is None:
        try:
            DRIVER = get_neo4j_driver()
            DRIVER.verify_connectivity()
        except Exception as exc:
            raise RuntimeError(
                'Neo4j Aura routing is not connected. Set NEO4J_URI (or NEO4J_INSTANCE_ID), NEO4J_USERNAME, and NEO4J_PASSWORD, then rerun the Neo4j section if needed.'
            ) from exc
    return DRIVER


DATASTORE_COVERAGE_CYPHER = """
MATCH (d:DataStore {demo_id: $demo_id})-[r:COVERS]->(c)
WHERE c.name_normalized IN $terms
RETURN d.name AS datastore, labels(c)[0] AS concept_type, c.name AS matched_term, r.count AS coverage_count
ORDER BY coverage_count DESC, datastore, concept_type, matched_term
""".strip()

DATASTORE_OVERLAP_CYPHER = """
MATCH (left:DataStore {demo_id: $demo_id})-[r:OVERLAPS_WITH]->(right:DataStore {demo_id: $demo_id})
RETURN left.name AS left_datastore, right.name AS right_datastore, r.score AS score, r.shared_types AS shared_types, r.shared_terms AS shared_terms
ORDER BY score DESC, left_datastore, right_datastore
""".strip()


def reset_demo_graph(driver) -> None:
    driver.execute_query(
        'MATCH (n {demo_id: $demo_id}) DETACH DELETE n',
        routing_=RoutingControl.WRITE,
        demo_id=DEMO_ID,
    )


def ingest_demo_graph(driver, coverage_rows: list[dict[str, Any]], overlap_rows: list[dict[str, Any]]) -> None:
    datastore_rows = [
        {
            'name': repository,
            'description': STORE_DESCRIPTIONS[repository],
        }
        for repository in REPOSITORY_ORDER
    ]
    driver.execute_query(
        """
        UNWIND $rows AS row
        MERGE (d:DataStore {demo_id: $demo_id, name: row.name})
        SET d.description = row.description
        """,
        routing_=RoutingControl.WRITE,
        demo_id=DEMO_ID,
        rows=datastore_rows,
    )

    for label in ['Region', 'Variety', 'Disease', 'Process', 'QualityEffect', 'Keyword']:
        rows = [row for row in coverage_rows if row['term_type'] == label]
        if not rows:
            continue
        query = f"""
        UNWIND $rows AS row
        MATCH (d:DataStore {{demo_id: $demo_id, name: row.datastore}})
        MERGE (c:{label} {{demo_id: $demo_id, name_normalized: row.term_normalized}})
        SET c.name = row.term
        MERGE (d)-[r:COVERS {{demo_id: $demo_id, term_type: row.term_type, term_normalized: row.term_normalized}}]->(c)
        SET r.count = row.count
        """
        driver.execute_query(
            query,
            routing_=RoutingControl.WRITE,
            demo_id=DEMO_ID,
            rows=rows,
        )

    overlap_edge_rows: list[dict[str, Any]] = []
    for row in overlap_rows:
        overlap_edge_rows.append(row)
        overlap_edge_rows.append(
            {
                'left_datastore': row['right_datastore'],
                'right_datastore': row['left_datastore'],
                'shared_terms': row['shared_terms'],
                'shared_types': row['shared_types'],
                'score': row['score'],
            }
        )

    driver.execute_query(
        """
        UNWIND $rows AS row
        MATCH (left:DataStore {demo_id: $demo_id, name: row.left_datastore})
        MATCH (right:DataStore {demo_id: $demo_id, name: row.right_datastore})
        MERGE (left)-[r:OVERLAPS_WITH {demo_id: $demo_id, target: row.right_datastore}]->(right)
        SET r.shared_terms = row.shared_terms,
            r.shared_types = row.shared_types,
            r.score = row.score
        """,
        routing_=RoutingControl.WRITE,
        demo_id=DEMO_ID,
        rows=overlap_edge_rows,
    )


def route_datastores_with_neo4j(triage: QuestionTriage) -> list[dict[str, Any]]:
    driver = require_driver()
    requested_terms = [normalize_text(term) for term in triage_terms(triage)]
    if not requested_terms:
        return []
    records = driver.execute_query(
        """
        MATCH (d:DataStore {demo_id: $demo_id})-[r:COVERS]->(c)
        WHERE c.name_normalized IN $terms
        WITH d, collect(DISTINCT c.name) AS matched_terms, collect(DISTINCT labels(c)[0]) AS matched_types, sum(coalesce(r.count, 1)) AS score
        RETURN d.name AS datastore, matched_terms, matched_types, score
        ORDER BY score DESC, datastore
        """,
        routing_=RoutingControl.READ,
        demo_id=DEMO_ID,
        terms=requested_terms,
    ).records
    ranked = [record.data() for record in records]
    desired_count = 2 if triage.requested_outcome == 'mixed' else 1
    return ranked[:desired_count]

# %% [markdown]
# ### Load Aggregated Metadata For Neo4j From Files
# Duplicate the frontmatter-loading logic here so the graph section can be run from scratch.

# %%
neo4j_documents: list[dict[str, Any]] = []

for path in sorted((DATA_ROOT / 'vine_diseases').glob('*.md')):
    post = frontmatter.load(path)
    metadata = MetadataExtraction.model_validate(post.metadata['metadata']).model_dump(mode='json')
    metadata['regions'] = clean_list([post.metadata.get('country', ''), post.metadata.get('region', ''), *metadata['regions']])
    neo4j_documents.append(
        {
            'document_id': str(path.relative_to(PROJECT_ROOT)),
            'title': post.metadata['title'],
            'repository': post.metadata['repository'],
            'country': post.metadata.get('country', ''),
            'region': post.metadata.get('region', ''),
            'source': post.metadata.get('source', ''),
            'source_urls': list(post.metadata.get('source_urls', [])),
            'source_path': str(path.relative_to(PROJECT_ROOT)),
            'content': post.content.strip(),
            'metadata': metadata,
            'keyword_blob': ' | '.join(
                piece
                for piece in [
                    post.metadata['title'],
                    post.metadata.get('country', ''),
                    post.metadata.get('region', ''),
                    metadata['summary'],
                    *metadata['regions'],
                    *metadata['varieties'],
                    *metadata['diseases'],
                    *metadata['winemaking_steps'],
                    *metadata['quality_effects'],
                    *metadata['keywords'],
                ]
                if piece
            ),
        }
    )

for path in sorted((DATA_ROOT / 'wine_diseases').glob('*.md')):
    post = frontmatter.load(path)
    metadata = MetadataExtraction.model_validate(post.metadata['metadata']).model_dump(mode='json')
    metadata['regions'] = clean_list([post.metadata.get('country', ''), post.metadata.get('region', ''), *metadata['regions']])
    neo4j_documents.append(
        {
            'document_id': str(path.relative_to(PROJECT_ROOT)),
            'title': post.metadata['title'],
            'repository': post.metadata['repository'],
            'country': post.metadata.get('country', ''),
            'region': post.metadata.get('region', ''),
            'source': post.metadata.get('source', ''),
            'source_urls': list(post.metadata.get('source_urls', [])),
            'source_path': str(path.relative_to(PROJECT_ROOT)),
            'content': post.content.strip(),
            'metadata': metadata,
            'keyword_blob': ' | '.join(
                piece
                for piece in [
                    post.metadata['title'],
                    post.metadata.get('country', ''),
                    post.metadata.get('region', ''),
                    metadata['summary'],
                    *metadata['regions'],
                    *metadata['varieties'],
                    *metadata['diseases'],
                    *metadata['winemaking_steps'],
                    *metadata['quality_effects'],
                    *metadata['keywords'],
                ]
                if piece
            ),
        }
    )

for path in sorted((DATA_ROOT / 'wine_making').glob('*.md')):
    post = frontmatter.load(path)
    metadata = MetadataExtraction.model_validate(post.metadata['metadata']).model_dump(mode='json')
    metadata['regions'] = clean_list([post.metadata.get('country', ''), post.metadata.get('region', ''), *metadata['regions']])
    neo4j_documents.append(
        {
            'document_id': str(path.relative_to(PROJECT_ROOT)),
            'title': post.metadata['title'],
            'repository': post.metadata['repository'],
            'country': post.metadata.get('country', ''),
            'region': post.metadata.get('region', ''),
            'source': post.metadata.get('source', ''),
            'source_urls': list(post.metadata.get('source_urls', [])),
            'source_path': str(path.relative_to(PROJECT_ROOT)),
            'content': post.content.strip(),
            'metadata': metadata,
            'keyword_blob': ' | '.join(
                piece
                for piece in [
                    post.metadata['title'],
                    post.metadata.get('country', ''),
                    post.metadata.get('region', ''),
                    metadata['summary'],
                    *metadata['regions'],
                    *metadata['varieties'],
                    *metadata['diseases'],
                    *metadata['winemaking_steps'],
                    *metadata['quality_effects'],
                    *metadata['keywords'],
                ]
                if piece
            ),
        }
    )

neo4j_coverage_rows = build_coverage_rows(neo4j_documents)
neo4j_overlap_rows = build_overlap_rows(neo4j_coverage_rows)
pd.DataFrame(neo4j_coverage_rows).groupby(['datastore', 'term_type']).size().rename('rows').reset_index()

# %% [markdown]
# ### Seed Neo4j Aura Graph
# Create the aggregated graph from the frontmatter-derived metadata.

# %%
neo4j_seed_driver = get_neo4j_driver()
neo4j_seed_driver.verify_connectivity()
reset_demo_graph(neo4j_seed_driver)
ingest_demo_graph(neo4j_seed_driver, neo4j_coverage_rows, neo4j_overlap_rows)
neo4j_seed_driver.close()
'Aggregated graph created.'

# %% [markdown]
# ### Reconnect To Aura From Scratch
# Open a fresh connection after seeding so the live query cells start from a clean client.

# %%
DRIVER = get_neo4j_driver()
DRIVER.verify_connectivity()
'Connected to Neo4j Aura.'

# %%
manual_terms = ['gray rot', 'botrytis cinerea', 'clarification', 'filtration']
coverage_records = DRIVER.execute_query(
    DATASTORE_COVERAGE_CYPHER,
    routing_=RoutingControl.READ,
    demo_id=DEMO_ID,
    terms=[normalize_text(term) for term in manual_terms],
).records
pd.DataFrame(record.data() for record in coverage_records)

# %%
overlap_records = DRIVER.execute_query(
    DATASTORE_OVERLAP_CYPHER,
    routing_=RoutingControl.READ,
    demo_id=DEMO_ID,
).records
pd.DataFrame(record.data() for record in overlap_records)

# %% [markdown]
# ## LangGraph Runtime
# Runtime graph: `triage_question -> route_with_neo4j -> retrieve_from_selected_datastores -> synthesize_answer`
# No `RuntimeContext` is used here; the notebook globals act as the fixed dependencies.

# %%
class State(TypedDict, total=False):
    question: str
    triage: dict[str, Any]
    matched_graph_terms: list[str]
    selected_datastores: list[str]
    tool_requests: list[dict[str, Any]]
    retrieval_results: list[dict[str, Any]]
    final_answer: str


async def triage_question_node(state: State) -> dict[str, Any]:
    result = await triage_agent.run(f"User question:\n{state['question']}")
    triage = result.output
    return {'triage': triage.model_dump(mode='json')}


def route_with_neo4j_node(state: State) -> dict[str, Any]:
    triage = QuestionTriage.model_validate(state['triage'])
    routed = route_datastores_with_neo4j(triage)
    return {
        'matched_graph_terms': clean_list(term for row in routed for term in row['matched_terms']),
        'selected_datastores': [row['datastore'] for row in routed],
        'tool_requests': routed,
    }


async def retrieve_from_selected_datastores_node(state: State) -> dict[str, Any]:
    triage = QuestionTriage.model_validate(state['triage'])
    tasks = []
    for datastore in state['selected_datastores']:
        if datastore == 'wine_making':
            tasks.append(qdrant_tool(state['question'], triage))
        else:
            tasks.append(sqlite_tool(state['question'], triage, datastore))
    retrieval_results = await asyncio.gather(*tasks)
    return {'retrieval_results': retrieval_results}


async def synthesize_answer_node(state: State) -> dict[str, Any]:
    retrieval_text = '\n\n'.join(
        f"[{result['datastore']}]\n{result['text']}"
        for result in state['retrieval_results']
        if result['text']
    )
    prompt = f"""
    User question:
    {state['question']}

    Retrieved text results:
    {retrieval_text}
    """.strip()
    final_answer = (await final_answer_agent.run(prompt)).output
    return {'final_answer': final_answer.answer}


workflow_builder = StateGraph(State)
workflow_builder.add_node('triage_question', triage_question_node)
workflow_builder.add_node('route_with_neo4j', route_with_neo4j_node)
workflow_builder.add_node('retrieve_from_selected_datastores', retrieve_from_selected_datastores_node)
workflow_builder.add_node('synthesize_answer', synthesize_answer_node)
workflow_builder.add_edge(START, 'triage_question')
workflow_builder.add_edge('triage_question', 'route_with_neo4j')
workflow_builder.add_edge('route_with_neo4j', 'retrieve_from_selected_datastores')
workflow_builder.add_edge('retrieve_from_selected_datastores', 'synthesize_answer')
workflow_builder.add_edge('synthesize_answer', END)
wine_demo_workflow = workflow_builder.compile()

# %% [markdown]
# ## Live Questions
# Each question has its own section so the exact wording stays visible during the demo.

# %% [markdown]
# ## Demo Question 1
# Goal: show a single-store route into the vineyard disease datastore.
# 
# Question:
# "Which cultivars look safest for central Poland if fungal diseases are the main constraint?"

# %%
question_1 = 'Which cultivars look safest for central Poland if fungal diseases are the main constraint?'
question_1_result = await wine_demo_workflow.ainvoke({'question': question_1})
question_1_titles = []
for item in question_1_result['retrieval_results']:
    top_result = item.get('top_result')
    if isinstance(top_result, dict) and top_result:
        question_1_titles.append(top_result['title'])
    elif top_result is not None and getattr(top_result, 'payload', None):
        question_1_titles.append(top_result.payload.get('title'))
    else:
        question_1_titles.append(None)

{
    'question': question_1,
    'selected_datastores': question_1_result['selected_datastores'],
    'matched_graph_terms': question_1_result['matched_graph_terms'],
    'retrieval_titles': question_1_titles,
    'final_answer': question_1_result['final_answer'],
}

# %% [markdown]
# ## Demo Question 2
# Goal: show a single-store route into the wine quality datastore.
# 
# Question:
# "What signs tell a French winery that gray rot is already hurting wine quality?"

# %%
question_2 = 'What signs tell a French winery that gray rot is already hurting wine quality?'
question_2_result = await wine_demo_workflow.ainvoke({'question': question_2})
question_2_titles = []
for item in question_2_result['retrieval_results']:
    top_result = item.get('top_result')
    if isinstance(top_result, dict) and top_result:
        question_2_titles.append(top_result['title'])
    elif top_result is not None and getattr(top_result, 'payload', None):
        question_2_titles.append(top_result.payload.get('title'))
    else:
        question_2_titles.append(None)

{
    'question': question_2,
    'selected_datastores': question_2_result['selected_datastores'],
    'matched_graph_terms': question_2_result['matched_graph_terms'],
    'retrieval_titles': question_2_titles,
    'final_answer': question_2_result['final_answer'],
}

# %% [markdown]
# ## Demo Question 3
# Goal: show a two-store fan-out that combines disease impact with cellar handling.
# 
# Question:
# "Gray rot affected Pinot Noir grapes in France. How can it change wine quality, and what cellar step helps reduce clarification or filtration problems?"

# %%
question_3 = 'Gray rot affected Pinot Noir grapes in France. How can it change wine quality, and what cellar step helps reduce clarification or filtration problems?'
question_3_result = await wine_demo_workflow.ainvoke({'question': question_3})
question_3_titles = []
for item in question_3_result['retrieval_results']:
    top_result = item.get('top_result')
    if isinstance(top_result, dict) and top_result:
        question_3_titles.append(top_result['title'])
    elif top_result is not None and getattr(top_result, 'payload', None):
        question_3_titles.append(top_result.payload.get('title'))
    else:
        question_3_titles.append(None)

{
    'question': question_3,
    'selected_datastores': question_3_result['selected_datastores'],
    'matched_graph_terms': question_3_result['matched_graph_terms'],
    'retrieval_titles': question_3_titles,
    'final_answer': question_3_result['final_answer'],
}
