# %% [markdown]
# # From RAG To Knowledge Graphs In 2027: Neo4j Demo
# Notebook-style Python cells for manual copy-paste into Jupyter.

# %% [markdown]
# ## Setup
# Fill in `.env` before running the extraction or Neo4j cells.

# %%
import json
import os
import runpy
from pathlib import Path
from typing import Any

import frontmatter
import pandas as pd
from dotenv import load_dotenv
from neo4j import GraphDatabase, Result, RoutingControl
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_ai import Agent

# %%
load_dotenv()

PROJECT_ROOT = Path.cwd()
INPUT_PATHS = sorted(PROJECT_ROOT.glob("data/*.md"))
PROCESSED_DIR = PROJECT_ROOT / "processed"
JSONL_PATH = PROCESSED_DIR / "graph_extractions.jsonl"

MODEL_NAME = os.getenv("KG_DEMO_MODEL", "openai:gpt-4.1-mini")
NEO4J_URI = os.getenv("NEO4J_URI", "neo4j+s://<instance>.databases.neo4j.io")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "<password>")

print(f"Input files: {len(INPUT_PATHS)}")
print(f"Processed dir: {PROCESSED_DIR}")
print(f"Model: {MODEL_NAME}")
print(f"Neo4j URI: {NEO4J_URI}")

# %% [markdown]
# ## Inspect The Corpus
# Each file should have frontmatter like `title`, `source`, `date_published`, `author`, and `url`.

# %%
if not INPUT_PATHS:
    raise RuntimeError("No markdown files found in data/*.md")

INPUT_PATHS[:10]

# %%
sample_path = INPUT_PATHS[0]
sample_post = frontmatter.load(sample_path)

print(sample_path)
print(sample_post.metadata)
print()
print(sample_post.content[:1200])

# %% [markdown]
# ## Define The Extraction Schema
# `source_type` is removed. It does not change extraction quality, ingestion, or the demo queries.

# %%
class DocumentGraphExtraction(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    summary: str = Field(description="A concise 2-4 sentence summary.")
    technologies: list[str] = Field(default_factory=list)
    concepts: list[str] = Field(default_factory=list)
    business_topics: list[str] = Field(default_factory=list)
    people: list[str] = Field(default_factory=list)
    organizations: list[str] = Field(default_factory=list)

    @field_validator(
        "technologies", "concepts", "business_topics", "people", "organizations", mode="before"
    )
    @classmethod
    def ensure_list(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return list(value)

    @field_validator("technologies", "concepts", "business_topics", "people", "organizations")
    @classmethod
    def dedupe_and_clean(cls, values: list[str]) -> list[str]:
        seen: set[str] = set()
        cleaned_values: list[str] = []
        for value in values:
            cleaned = " ".join(str(value).split()).strip()
            if not cleaned or cleaned.casefold() in seen:
                continue
            seen.add(cleaned.casefold())
            cleaned_values.append(cleaned)
        return cleaned_values


DocumentGraphExtraction.model_json_schema()

# %% [markdown]
# ## Load The Prompt
# The prompt lives in `prompts/graph-metadata-extractor.py`, as the plan required.

# %%
GRAPH_METADATA_EXTRACTOR = runpy.run_path(
    PROJECT_ROOT / "prompts" / "graph-metadata-extractor.py"
)["GRAPH_METADATA_EXTRACTOR"]

print(GRAPH_METADATA_EXTRACTOR)

# %% [markdown]
# ## Create The Extraction Agent

# %%
extraction_agent = Agent(
    MODEL_NAME,
    instructions=GRAPH_METADATA_EXTRACTOR,
    output_type=DocumentGraphExtraction,
)

# %% [markdown]
# ## Run Extraction On One Document
# This is the low-risk live path.

# %%
one_result = await extraction_agent.run(
    f"""
    Extract graph-friendly metadata from this markdown document body.

    <document_body>
    {sample_post.content}
    </document_body>
    """.strip()
)

one_result.output

# %% [markdown]
# ## Run Extraction Across `data/*.md`
# This is the pre-talk batch step. Each completed extraction is appended to JSONL immediately.

# %%
extractions: list[dict[str, Any]] = []
PROCESSED_DIR.mkdir(exist_ok=True)

with JSONL_PATH.open("w", encoding="utf-8") as jsonl_file:
    for path in INPUT_PATHS:
        post = frontmatter.load(path)
        result = await extraction_agent.run(
            f"""
            Extract graph-friendly metadata from this markdown document body.

            <document_body>
            {post.content}
            </document_body>
            """.strip()
        )
        extraction = result.output
        record = {
            "source_path": str(path.relative_to(PROJECT_ROOT)),
            "document_id": post.metadata.get("url") or str(path.relative_to(PROJECT_ROOT)),
            "metadata": dict(post.metadata),
            "graph": extraction.model_dump(mode="json"),
        }
        jsonl_file.write(json.dumps(record, ensure_ascii=False) + "\n")
        jsonl_file.flush()
        extractions.append({"path": path, "post": post, "extraction": extraction})

print(f"Wrote {len(extractions)} JSONL records to {JSONL_PATH}")

len(extractions)

# %%
pd.DataFrame(
    [
        {
            "path": str(item["path"]),
            "technologies": item["extraction"].technologies,
            "concepts": item["extraction"].concepts,
            "business_topics": item["extraction"].business_topics,
            "people": item["extraction"].people,
            "organizations": item["extraction"].organizations,
        }
        for item in extractions
    ]
)

# %% [markdown]
# ## Write Enriched Outputs
# The processed files keep the original body and add `graph` data to frontmatter.

# %%
PROCESSED_DIR.mkdir(exist_ok=True)

for item in extractions:
    path = item["path"]
    post = item["post"]
    extraction = item["extraction"]
    metadata = dict(post.metadata)
    metadata["document_id"] = metadata.get("url") or str(path)
    metadata["graph"] = extraction.model_dump(mode="json")
    frontmatter.dump(frontmatter.Post(post.content, **metadata), PROCESSED_DIR / path.name)

print(f"Wrote {len(extractions)} processed markdown files to {PROCESSED_DIR}")

# %%
processed_paths = sorted(PROCESSED_DIR.glob("*.md"))
if not processed_paths:
    raise RuntimeError("No processed markdown files found in processed/")

processed_sample = frontmatter.load(processed_paths[0])
print(processed_paths[0])
print(processed_sample.metadata)
print()
print(processed_sample.content[:800])

# %% [markdown]
# ## Ontology
# Labels: `Document`, `Source`, `Technology`, `Concept`, `BusinessTopic`, `Person`, `Organization`.
# Relationships: `FROM_SOURCE`, `MENTIONS_TECHNOLOGY`, `MENTIONS_CONCEPT`, `MENTIONS_BUSINESS_TOPIC`, `MENTIONS_PERSON`, `MENTIONS_ORGANIZATION`.

# %% [markdown]
# ## Connect To Neo4j Aura
# Create the driver once in the notebook and reuse it in later cells.
# Use the Aura database credentials from the downloaded credentials file.

# %%
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
driver.verify_connectivity()


def cypher_write(query: str, **params: Any):
    return driver.execute_query(
        query,
        routing_=RoutingControl.WRITE,
        **params,
    )


def cypher_df(query: str, **params: Any):
    return driver.execute_query(
        query,
        routing_=RoutingControl.READ,
        result_transformer_=Result.to_df,
        **params,
    )

# %% [markdown]
# ## Create Constraints

# %%
constraint_queries = [
    "CREATE CONSTRAINT document_document_id IF NOT EXISTS FOR (d:Document) REQUIRE d.document_id IS UNIQUE",
    "CREATE CONSTRAINT source_name IF NOT EXISTS FOR (s:Source) REQUIRE s.name IS UNIQUE",
    "CREATE CONSTRAINT technology_name IF NOT EXISTS FOR (n:Technology) REQUIRE n.name IS UNIQUE",
    "CREATE CONSTRAINT concept_name IF NOT EXISTS FOR (n:Concept) REQUIRE n.name IS UNIQUE",
    "CREATE CONSTRAINT business_topic_name IF NOT EXISTS FOR (n:BusinessTopic) REQUIRE n.name IS UNIQUE",
    "CREATE CONSTRAINT person_name IF NOT EXISTS FOR (n:Person) REQUIRE n.name IS UNIQUE",
    "CREATE CONSTRAINT organization_name IF NOT EXISTS FOR (n:Organization) REQUIRE n.name IS UNIQUE",
]

for query in constraint_queries:
    cypher_write(query)

print("Constraints created.")

# %% [markdown]
# ## Ingest Documents

# %%
entity_specs = [
    ("technologies", "Technology", "MENTIONS_TECHNOLOGY"),
    ("concepts", "Concept", "MENTIONS_CONCEPT"),
    ("business_topics", "BusinessTopic", "MENTIONS_BUSINESS_TOPIC"),
    ("people", "Person", "MENTIONS_PERSON"),
    ("organizations", "Organization", "MENTIONS_ORGANIZATION"),
]

for path in processed_paths:
    post = frontmatter.load(path)
    metadata = dict(post.metadata)
    graph = metadata["graph"]
    document_id = metadata.get("document_id") or metadata.get("url") or str(path)

    cypher_write(
        """
        MERGE (d:Document {document_id: $document_id})
        SET d.title = $title,
            d.author = $author,
            d.date_published = $date_published,
            d.url = $url,
            d.summary = $summary
        MERGE (s:Source {name: $source})
        MERGE (d)-[:FROM_SOURCE]->(s)
        """,
        document_id=document_id,
        title=metadata.get("title") or path.stem,
        author=metadata.get("author"),
        date_published=metadata.get("date_published"),
        url=metadata.get("url"),
        summary=graph["summary"],
        source=metadata.get("source") or "Unknown source",
    )
    for field_name, label, relationship in entity_specs:
        for name in graph[field_name]:
            cypher_write(
                f"""
                MATCH (d:Document {{document_id: $document_id}})
                MERGE (e:{label} {{name: $name}})
                MERGE (d)-[:{relationship}]->(e)
                """,
                document_id=document_id,
                name=name,
            )

print(f"Ingested {len(processed_paths)} documents.")

# %% [markdown]
# ## Query 1: Documents And Sources

# %%
query_1 = """
MATCH (d:Document)-[:FROM_SOURCE]->(s:Source)
RETURN d.title AS document, s.name AS source
ORDER BY source, document
LIMIT 25
"""

cypher_df(query_1)

# %% [markdown]
# ## Query 2: Documents Mentioning One Entity

# %%
entity_name = "Neo4j"

query_2 = """
MATCH (d:Document)-[:MENTIONS_TECHNOLOGY|MENTIONS_CONCEPT]->(e)
WHERE e.name = $entity_name
RETURN e.name AS entity, d.title AS document
ORDER BY document
"""

cypher_df(query_2, entity_name=entity_name)

# %% [markdown]
# ## Query 3: Business Topics Across Sources

# %%
query_3 = """
MATCH (d:Document)-[:FROM_SOURCE]->(s:Source)
MATCH (d)-[:MENTIONS_BUSINESS_TOPIC]->(b:BusinessTopic)
WITH b, collect(DISTINCT s.name) AS sources, count(DISTINCT d) AS document_count
WHERE size(sources) > 1
RETURN b.name AS business_topic, document_count, sources
ORDER BY document_count DESC, business_topic
LIMIT 20
"""

cypher_df(query_3)

# %% [markdown]
# ## Query 4: Neighborhood Of One Document

# %%
document_id = frontmatter.load(processed_paths[0]).metadata["document_id"]

query_4 = """
MATCH (d:Document {document_id: $document_id})
OPTIONAL MATCH (d)-[:FROM_SOURCE]->(s:Source)
OPTIONAL MATCH (d)-[r]->(e)
WHERE e:Technology OR e:Concept OR e:BusinessTopic OR e:Person OR e:Organization
RETURN d.title AS document, s.name AS source, type(r) AS relationship, e.name AS entity
ORDER BY relationship, entity
"""

cypher_df(query_4, document_id=document_id)

# %% [markdown]
# ## Close The Driver

# %%
driver.close()
