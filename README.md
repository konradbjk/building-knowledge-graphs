# Building Knowledge Graphs

This repository is an exploratory notebook project for turning technical content into structured knowledge that can be searched, indexed, stored, and visualized as graphs.

The main workflow lives in [knowledge_ingestion_and_graph_exploration.ipynb](/Users/konrad/Projects/building-knowledge-graphs/knowledge_ingestion_and_graph_exploration.ipynb). The notebook started as `test_processing.ipynb` and was renamed to reflect what it actually does.

## What The Notebook Covers

The notebook walks through a full experimental pipeline:

1. Load local MDX articles with frontmatter metadata.
2. Clean and normalize article content.
3. Convert articles into LangChain `Document` objects.
4. Use an LLM to extract structured metadata such as technologies, concepts, difficulty, and section summaries.
5. Split enriched content into smaller units for retrieval.
6. Index those units in Qdrant with embeddings.
7. Ingest YouTube videos and playlists, attach transcript and video metadata, and prepare them as documents.
8. Save and load documents from MongoDB.
9. Build NetworkX graphs from extracted technologies and concepts.
10. Export interactive graph visualizations with PyVis.

## Repository Layout

- [knowledge_ingestion_and_graph_exploration.ipynb](/Users/konrad/Projects/building-knowledge-graphs/knowledge_ingestion_and_graph_exploration.ipynb): exploratory end-to-end notebook
- [pyproject.toml](/Users/konrad/Projects/building-knowledge-graphs/pyproject.toml): project dependencies managed with `uv`
- [uv.lock](/Users/konrad/Projects/building-knowledge-graphs/uv.lock): locked dependency versions

## Setup

The project uses Python 3.12+ and is configured for `uv`.

```bash
uv sync
uv run jupyter notebook
```

If you want to run the notebook end to end, the current workflow expects several external services and credentials to exist locally.

## Expected Inputs And Services

### Local content

The notebook references local content that is not included in this repository:

- `articles/<SAMPLE_ARTICLE_NAME>.mdx`
- `tutorials/*.mdx`
- `sample.jsonl`
- `local_documents.jsonl`

The MDX files are expected to contain frontmatter fields such as:

- `title`
- `description`
- `image`

### Environment variables

The notebook loads environment variables via `.env` and uses at least:

- `GOOGLE_DEVELOPER_KEY` for YouTube Data API requests

There are also placeholder URLs in the notebook such as `https://<BLOG_URL>/...` that should be replaced with your actual site URL if you want article links in metadata to be valid.

### External dependencies

The notebook assumes these services are available:

- Qdrant at `http://localhost:6333`
- MongoDB at `mongodb://admin:1234example@localhost:27017/`
- Azure OpenAI access for `gpt-4.1` / `gpt-4.1-mini`
- OpenAI embeddings for vector indexing
- spaCy model `en_core_web_sm`

For spaCy, install the model separately if it is not already present:

```bash
uv run python -m spacy download en_core_web_sm
```

## Pipeline Details

### 1. MDX ingestion

The notebook defines:

- `clean_markdown_content()` to strip formatting and reduce MDX content to plain text
- `parse_mdx_file()` to extract frontmatter and build canonical article metadata
- `MDXLoader` and `MDXDirectoryLoader` to turn files into LangChain documents

This is the local article ingestion layer.

### 2. Metadata extraction with LLMs

The notebook builds a prompt template that asks an LLM to extract:

- technologies
- concepts
- difficulty analysis
- difficulty level
- required skills
- section summaries

The output is parsed as JSON and merged back into document metadata so each section can be indexed separately.

### 3. Self-query preparation

The notebook experiments with LangChain structured query generation for fields such as:

- `technologies`
- `concepts`

This is intended to support metadata-aware retrieval against Qdrant.

### 4. Vector indexing

The `ContentIndexedChunker` and `index_content()` helpers convert enriched content into retrieval chunks and push them into a Qdrant collection.

The current default collection name is `tutorials`.

### 5. YouTube ingestion

The notebook uses:

- `YoutubeLoader` for transcript loading
- `pytube.Playlist` for playlist traversal
- direct YouTube Data API calls for video metadata

Each video document is enriched with fields such as title, description, publish date, views, likes, comments, duration, and source URL.

### 6. MongoDB persistence

The notebook includes helper functions to:

- insert LangChain documents into MongoDB
- delete inserted documents by `_id`
- load stored documents back into LangChain `Document` objects

This acts as a simple persistence layer for the knowledge base.

### 7. Graph construction

The notebook finishes with several graph experiments:

- keyword-to-concept graph construction
- multi-dimensional graph construction across content, technologies, concepts, and difficulty
- content-to-content similarity graph using Jaccard similarity
- community detection and identification of highly connected bridge documents

Interactive graph views are exported as HTML through PyVis.

## Outputs

Depending on which sections you run, the notebook can produce:

- LangChain `Document` collections
- enriched metadata JSON objects
- Qdrant collections
- MongoDB records
- interactive HTML graph visualizations such as:
  - `multi_dimensional_graph.html`
  - `content_similarity_graph.html`

## Current State

This repository is centered on one exploratory notebook rather than a packaged library or application. Some paths, credentials, hostnames, and sample data references are placeholders or local-only values, so the notebook is best treated as a prototype and reference workflow.
