# Repository Guidelines

## Project Overview

This repository is a working space for talk material about knowledge graphs, retrieval, and AI-assisted content analysis. The main deliverables are Jupyter notebooks used to prepare and rehearse talks, test ideas, and keep runnable examples close to the presentation narrative.

The current theme is knowledge-graph-oriented retrieval rather than generic chatbot infrastructure. Recent talk titles include `From RAG to Knowledge Graphs in 2027`, and the repository should support future talks in the same style.

## Notebook Organization

Each talk title should have its own dedicated notebook. Do not keep stacking unrelated talks into one long exploratory file once a talk direction is clear.

Recommended naming pattern:

- `from_rag_to_knowledge_graphs_in_2027.ipynb`
- `knowledge_graphs_for_<topic>.ipynb`
- `talk_<short_title>.ipynb`

If an existing notebook evolves from a scratchpad into talk material, rename it to match the actual talk or topic. Keep exploratory throwaway naming like `test_*.ipynb` out of the main repository state once the notebook has a real purpose.

## Technical Direction

`pydantic-ai` is the active LLM framework in this repository. Do not introduce new LangChain-based notebook code for prompting, structured outputs, or model orchestration unless there is a concrete gap that `pydantic-ai` cannot cover.

Qdrant, MongoDB, NetworkX, PyVis, frontmatter parsing, and general Python data tooling are all in scope when they support the talk workflow. Keep the stack small and explicit. If a notebook only needs plain Python data structures, use them instead of framework abstractions.

## Code And Notebook Conventions

Prefer notebooks that read as a narrative:

1. ingest source material
2. enrich or extract metadata
3. index or persist the results
4. analyze graph structure
5. visualize outputs relevant to the talk

Keep helpers in the notebook when they are specific to one talk. Extract shared utilities only when multiple talk notebooks genuinely reuse them.

Use simple local models for notebook data, such as dataclasses or Pydantic models, instead of heavy framework-specific document wrappers when possible. Notebook examples should be easy to explain on stage.

## External Services And Credentials

Some notebooks depend on local services or credentials, typically:

- OpenAI- or Azure-compatible model access
- Qdrant running locally
- MongoDB running locally
- YouTube Data API credentials for playlist/video metadata

Do not assume those services are available when closing work. If a notebook path was not executed end to end because it needs local infrastructure or secrets, say so explicitly.

## Change Rules

When a user asks to update a notebook for a talk, preserve the presentation intent first and refactor second. The exact talk flow matters more than abstract cleanup.

When replacing an LLM framework or API surface, update the actual notebook code paths rather than only changing imports. If the old notebook relied on structured outputs, prompt templates, loaders, or vector-store wrappers, replace those pieces concretely and keep the new workflow runnable.

When documentation is likely to have changed, use current primary docs before changing the notebook. Do not rely on stale memory for fast-moving AI libraries.
