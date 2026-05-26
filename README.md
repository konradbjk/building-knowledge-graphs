# Building Knowledge Graphs

This repository is a working space for talk material about retrieval, structured extraction, and knowledge-graph-oriented analysis.

The current center of gravity is the demo flow for **From RAG To Knowledge Graphs In 2027**:

1. load markdown documents from `data/*.md`
2. extract graph-friendly metadata with `pydantic-ai`
3. persist the results as processed markdown and JSONL
4. ingest the extracted structure into Neo4j
5. run simple Cypher queries for exploration and presentation

## Current Deliverables

- [knowledge_extraction_neo4j_demo.py](/Users/konrad/Projects/building-knowledge-graphs/knowledge_extraction_neo4j_demo.py): notebook-style `# %%` Python file for the main extraction and Neo4j demo
- [from_rag_to_knowledge_graphs_in_2027_demo_plan.md](/Users/konrad/Projects/building-knowledge-graphs/from_rag_to_knowledge_graphs_in_2027_demo_plan.md): procedural plan for the demo notebook flow
- [prompts/graph-metadata-extractor.py](/Users/konrad/Projects/building-knowledge-graphs/prompts/graph-metadata-extractor.py): source-agnostic extraction prompt used by the Neo4j demo
- [knowledge_ingestion_and_graph_exploration.ipynb](/Users/konrad/Projects/building-knowledge-graphs/knowledge_ingestion_and_graph_exploration.ipynb): older exploratory notebook with broader ingestion and graph experiments
- [neo4j-intro.ipynb](/Users/konrad/Projects/building-knowledge-graphs/neo4j-intro.ipynb): smaller Neo4j connection and query scratchpad

## Main Demo Flow

The intended demo path is:

1. inspect markdown files in `data/*.md`
2. extract a small schema: `summary`, `technologies`, `concepts`, `business_topics`, `people`, `organizations`
3. append one JSON record per document to `processed/graph_extractions.jsonl`
4. write processed markdown files with `graph` data in frontmatter to `processed/*.md`
5. connect to Neo4j Aura with the Python driver
6. create constraints and ingest `Document`, `Source`, and extracted entity nodes
7. query the graph with `driver.execute_query(...)`

The notebook-style code is async-first on the extraction side and uses `await extraction_agent.run(...)` rather than synchronous wrappers.

## Repository Layout

- [knowledge_extraction_neo4j_demo.py](/Users/konrad/Projects/building-knowledge-graphs/knowledge_extraction_neo4j_demo.py): main demo code path
- [from_rag_to_knowledge_graphs_in_2027_demo_plan.md](/Users/konrad/Projects/building-knowledge-graphs/from_rag_to_knowledge_graphs_in_2027_demo_plan.md): demo plan
- [prompts/graph-metadata-extractor.py](/Users/konrad/Projects/building-knowledge-graphs/prompts/graph-metadata-extractor.py): extraction prompt for graph metadata
- [prompts/metadata-extractor.py](/Users/konrad/Projects/building-knowledge-graphs/prompts/metadata-extractor.py): earlier prompt reference
- [knowledge_ingestion_and_graph_exploration.ipynb](/Users/konrad/Projects/building-knowledge-graphs/knowledge_ingestion_and_graph_exploration.ipynb): exploratory notebook
- [neo4j-intro.ipynb](/Users/konrad/Projects/building-knowledge-graphs/neo4j-intro.ipynb): Neo4j scratchpad notebook
- [pyproject.toml](/Users/konrad/Projects/building-knowledge-graphs/pyproject.toml): project dependencies managed with `uv`
- [uv.lock](/Users/konrad/Projects/building-knowledge-graphs/uv.lock): locked dependency versions

## Setup

The project uses Python and is managed with `uv`.

```bash
uv sync
uv run jupyter notebook
```

The current dependency set includes:

- `pydantic-ai-slim[openai]`
- `neo4j`
- `python-frontmatter`
- `python-dotenv`
- `pandas`
- `networkx`
- `pyvis`
- `qdrant-client`
- `pymongo`

## Expected Inputs

The current Neo4j demo expects local markdown documents under `data/*.md`.

Each file should contain frontmatter similar to:

```md
---
title: Example title
source: Example source
date_published: 2024-11-03
author: Example author
url: https://example.com/article
---

Document body...
```

The extraction prompt is designed to reason from the document body only, not from frontmatter fields.

## Generated Artifacts

Running the main extraction flow can create:

- `processed/graph_extractions.jsonl`
  Purpose: append-friendly precomputed extraction records, one JSON object per document
- `processed/*.md`
  Purpose: processed markdown copies with extracted `graph` metadata stored in frontmatter

The JSONL file exists so the extraction batch can be reused later without rerunning the model step.

## Environment Variables

The repository uses `.env` for local configuration.

The current demo paths expect at least:

- `KG_DEMO_MODEL`
- `NEO4J_URI`
- `NEO4J_USERNAME`
- `NEO4J_PASSWORD`
- `GOOGLE_DEVELOPER_KEY` for the older YouTube-oriented notebook workflow

For Neo4j Aura, use the database credentials from the Aura credentials file. The current demo code assumes `driver.execute_query(...)` and routes read queries explicitly with `RoutingControl.READ`.

## Neo4j Notes

The current Neo4j demo uses:

- one reusable driver instance per notebook run
- `driver.execute_query(...)` rather than `session.run(...)` for the simple demo path
- `Result.to_df` for read queries that should display naturally in a notebook
- explicit read routing for read-only Cypher queries

The ontology is intentionally small:

- node labels: `Document`, `Source`, `Technology`, `Concept`, `BusinessTopic`, `Person`, `Organization`
- relationships: `FROM_SOURCE`, `MENTIONS_TECHNOLOGY`, `MENTIONS_CONCEPT`, `MENTIONS_BUSINESS_TOPIC`, `MENTIONS_PERSON`, `MENTIONS_ORGANIZATION`

## Older Exploratory Work

[knowledge_ingestion_and_graph_exploration.ipynb](/Users/konrad/Projects/building-knowledge-graphs/knowledge_ingestion_and_graph_exploration.ipynb) still contains broader experiments around:

- Qdrant indexing
- MongoDB persistence
- YouTube transcript and metadata ingestion
- NetworkX and PyVis graph construction

That notebook is still useful as reference material, but it is no longer the best entry point for the talk demo.

## Current State

This repository is still notebook-first rather than application-first. Some workflows depend on local services, credentials, and local markdown corpora that are not checked into the repository.

The extraction and Neo4j demo code was updated significantly during talk preparation, but it has not been fully re-run end to end in this repository after every change. Treat the repo as active working material rather than a frozen, fully reproducible package.
