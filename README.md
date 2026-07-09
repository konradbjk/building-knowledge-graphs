# Building Knowledge Graphs

This repository is a notebook-first workspace for talks about knowledge graphs, retrieval, and structured extraction. The main deliverables are runnable notebooks that stay close to the talk narrative instead of being packaged as an application.

## Main Notebook

- [ontologies-ocdi-neo4j-wearedevelopers.ipynb](/Users/konrad/Projects/building-knowledge-graphs/ontologies-ocdi-neo4j-wearedevelopers.ipynb): current WeAreDevelopers-oriented demo notebook. It combines metadata extraction, SQLite retrieval, Qdrant chunk retrieval, Neo4j datastore routing, and final answer synthesis in one notebook flow.

## Other Notebooks

- [knowledge_extraction_neo4j.ipynb](/Users/konrad/Projects/building-knowledge-graphs/knowledge_extraction_neo4j.ipynb): earlier extraction-to-Neo4j notebook path.
- [knowledge_ingestion_and_graph_exploration.ipynb](/Users/konrad/Projects/building-knowledge-graphs/knowledge_ingestion_and_graph_exploration.ipynb): broader ingestion, retrieval, and graph exploration notebook.
- [neo4j-intro.ipynb](/Users/konrad/Projects/building-knowledge-graphs/neo4j-intro.ipynb): small Neo4j connection and scratch notebook.

## Main Demo Flow

The current demo notebook is built around a three-store routing pattern:

1. load curated markdown briefs from `data/winde_demo/`
2. read extracted `metadata:` frontmatter for routing and filtering
3. use SQLite FTS for `vine_diseases` and `wine_diseases`
4. use Qdrant for chunk-level retrieval over `wine_making`
5. aggregate datastore coverage and overlap in Neo4j Aura
6. route a user question to the right datastore combination
7. synthesize a short final answer from retrieved evidence

## Repository Layout

- [prompts/](/Users/konrad/Projects/building-knowledge-graphs/prompts): prompt sources used by the notebooks.
- [misc/](/Users/konrad/Projects/building-knowledge-graphs/misc): support artifacts such as execution plans and exported notebook-style Python files. These are secondary to the notebooks and are not the main entrypoints.
- [pyproject.toml](/Users/konrad/Projects/building-knowledge-graphs/pyproject.toml): project dependencies managed with `uv`.
- [uv.lock](/Users/konrad/Projects/building-knowledge-graphs/uv.lock): locked dependency versions.

## Setup

Install dependencies and open the notebook environment:

```bash
uv sync
uv run jupyter notebook
```

## Services And Credentials

Not every notebook needs every service, but the current WeAreDevelopers demo expects some local or remote infrastructure:

- Azure-compatible OpenAI access for `pydantic-ai`
- Neo4j Aura credentials
- local Qdrant at `http://localhost:6333` for the chunk-retrieval path
- optional local MongoDB for broader exploration notebooks

Typical environment variables used across the current notebook set include:

- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_DEPLOYMENT` or `WINE_DEMO_MODEL`
- `COHERE_API_KEY`
- `COHERE_EMBED_MODEL`
- `NEO4J_URI` or `NEO4J_INSTANCE_ID`
- `NEO4J_USERNAME`
- `NEO4J_PASSWORD`
- `QDRANT_URL`
- `QDRANT_API_KEY`

## Data Expectations

The current notebook flow expects local markdown corpora with meaningful body text and structured frontmatter. For the wine demo, the corpus lives under `data/winde_demo/` and each document should carry `metadata:` frontmatter used for routing and retrieval.

## Notes

- The repository is intentionally notebook-first and talk-oriented.
- Some paths depend on local corpora, services, and secrets that are not checked into the repository.
- The notebooks are the primary interface. Files under `misc/` are support artifacts for planning or export, not the main workflow.
