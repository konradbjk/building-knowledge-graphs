# Neo4j Knowledge Extraction Demo Plan

Planning document for a beginner-friendly Jupyter notebook walkthrough.

## 1. Objective

Build a Jupyter notebook that demonstrates, step by step, how to:

1. read markdown documents from `data/*.md`
2. extract structured knowledge from those documents before the talk
3. save the extracted structure back into markdown frontmatter or adjacent artifacts
4. ingest that structure into Neo4j Aura
5. run a few simple Cypher queries over the ingested graph

This is a code walkthrough. The notebook should explain the code sections with markdown cells. It should not try to carry the talk’s conceptual argument by itself.

## 2. Constraints

- Audience: beginner-friendly
- Format: Jupyter notebook first, not slides
- Demo length: 10-15 minutes
- Extraction will usually be run before the talk
- Live steps should be low-risk and fast
- Input shape: markdown documents in `data/*.md`
- Documents are expected to have frontmatter with fields such as:
  - `title`
  - `source`
  - `date_published`
  - optional additional metadata
- Neo4j target: Aura / SaaS using a connection of the form:

```python
from neo4j import GraphDatabase

URI = "neo4j+s://<instance>.databases.neo4j.io"
AUTH = ("<instance-id>", "<password>")

with GraphDatabase.driver(URI, auth=AUTH) as driver:
    driver.verify_connectivity()
```

## 3. What The Notebook Should Actually Show

The notebook should be a walkthrough of a practical workflow:

1. inspect the input files
2. define the extraction schema
3. define the extraction prompt
4. run extraction on files in `data/*.md`
5. write enriched outputs
6. connect to Neo4j SaaS
7. ingest nodes and relationships
8. run beginner-friendly Cypher queries

Each notebook section should introduce the next code block, not try to summarize the whole talk.

## 4. Input Assumptions

The corpus can be mixed, but the prompt and pipeline must stay source-agnostic.

Each input document should be treated the same way:

```md
---
title: Example title
source: Smart Bear
date_published: 2024-11-03
author: Jason Cohen
url: https://example.com
---

Document body...
```

## 5. Recommended Notebook Structure

### Section 1: Setup

Purpose:
- imports
- environment variables
- Neo4j Aura connection variables
- model variables
- input/output path variables

Markdown cell goal:
- explain which variables need to be replaced before running the notebook

### Section 2: Inspect the corpus

Purpose:
- list files from `data/*.md`
- load frontmatter
- preview one or two documents

Markdown cell goal:
- explain the expected input format

### Section 3: Define the extraction schema

Purpose:
- create strict Pydantic output models
- keep the schema small enough for a beginner demo

Markdown cell goal:
- explain what we want to extract and why these fields map well to a graph

### Section 4: Define the extraction prompt

Purpose:
- create a reusable prompt in `prompts/graph-metadata-extractor.py`
- keep it close in style to [prompts/metadata-extractor.py](/Users/konrad/Projects/building-knowledge-graphs/prompts/metadata-extractor.py)

Markdown cell goal:
- explain that extraction is source-agnostic and based on document content only

### Section 5: Run extraction on markdown files

Purpose:
- loop through `data/*.md`
- send document content to the model
- capture strict structured output

Markdown cell goal:
- explain that this step is usually run before the talk, not live

### Section 6: Write enriched outputs

Purpose:
- save extracted fields back into markdown frontmatter or a parallel processed directory

Markdown cell goal:
- explain what gets saved and why this is useful for later ingestion

### Section 7: Define the Neo4j ontology

Purpose:
- show the node labels, core properties, and relationship types

Markdown cell goal:
- explain the graph model in beginner-friendly terms

### Section 8: Ingest into Neo4j Aura

Purpose:
- connect to Neo4j SaaS
- create constraints / indexes
- `MERGE` documents, entities, and relationships

Markdown cell goal:
- explain that the ingestion step is deterministic once extraction exists

### Section 9: Query with Cypher

Purpose:
- run 3-4 simple queries
- show useful graph traversals without making the Cypher overly advanced

Markdown cell goal:
- explain what each query is showing

## 6. Ontology V1

Keep the first ontology version small.

### Node labels

- `Document`
- `Source`
- `Technology`
- `Concept`
- `BusinessTopic`
- `Person`
- `Organization`

### Relationship types

- `(:Document)-[:FROM_SOURCE]->(:Source)`
- `(:Document)-[:MENTIONS_TECHNOLOGY]->(:Technology)`
- `(:Document)-[:MENTIONS_CONCEPT]->(:Concept)`
- `(:Document)-[:MENTIONS_BUSINESS_TOPIC]->(:BusinessTopic)`
- `(:Document)-[:MENTIONS_PERSON]->(:Person)`
- `(:Document)-[:MENTIONS_ORGANIZATION]->(:Organization)`
- optional later: `(:Entity)-[:RELATED_TO]->(:Entity)`

### Why this ontology first

It is easy to explain, easy to ingest, and easy to query.

It avoids trying to solve everything in v1.

## 7. Extraction Schema V1

The extraction schema should stay strict but small.

Recommended shape:

```json
{
  "source_type": "article|podcast_transcript|essay|other",
  "summary": "string",
  "technologies": ["string"],
  "concepts": ["string"],
  "business_topics": ["string"],
  "people": ["string"],
  "organizations": ["string"]
}
```

Notes:

- `technologies` should only include meaningful named technologies
- generic buzzwords such as `AI`, `LLM`, or `software` should not be included as technologies
- empty lists are valid and expected
- claims and relation extraction should be considered only after this smaller shape is working well

## 8. Prompt Design Rules

The prompt should stay close to the existing [prompts/metadata-extractor.py](/Users/konrad/Projects/building-knowledge-graphs/prompts/metadata-extractor.py) style:

- explicit objective
- explicit output rules
- strict JSON / structured output rules
- conservative extraction
- examples only if they are generic

The prompt should not:

- mention the talk title
- mention known corpus families
- use source metadata as a reasoning shortcut
- overfit to the current corpus

The prompt should focus only on the content of the current document.

## 9. Output Writing Strategy

There are three sensible options.

### Option A: overwrite frontmatter in a processed copy

Example:

- input: `data/example.md`
- output: `processed/example.md`

Benefits:

- easy to inspect
- easy to show live
- keeps enriched data attached to the document

### Option B: store extraction as adjacent JSON

Example:

- input: `data/example.md`
- output: `processed/example.json`

Benefits:

- cleaner separation between source text and extracted structure

Recommended choice:

- use processed markdown with enriched frontmatter for the demo

Reason:

- easier to explain in a notebook
- easier to inspect visually
- makes the “before / after” transformation obvious

### Option C: store batch extractions as JSONL

Example:

- input: `data/example.md`
- output: `processed/graph_extractions.jsonl`

Benefits:

- easy to reload ad-hoc without parsing markdown again
- compact precomputed artifact for notebook reruns
- one line per document makes it easy to filter, append, and inspect with CLI tools

Recommended secondary choice:

- keep JSONL as a precomputed support artifact in addition to processed markdown

Reason:

- the notebook can still show the markdown transformation live
- the JSONL file gives a low-friction fallback when extraction should not be rerun before a rehearsal or talk

## 10. Neo4j Aura Ingestion Plan

The code should start with visible variables that are easy to replace:

```python
NEO4J_URI = "neo4j+s://<instance>.databases.neo4j.io"
NEO4J_USERNAME = "<instance-id>"
NEO4J_PASSWORD = "<password>"
NEO4J_DATABASE = "neo4j"

INPUT_GLOB = "data/*.md"
PROCESSED_DIR = "processed/"
MODEL_NAME = "<model>"

RUN_EXTRACTION = False
RUN_INGESTION = False
```

The ingestion steps should be:

1. connect to Neo4j Aura
2. verify connectivity
3. create constraints
4. load processed markdown files
5. `MERGE` `Document`
6. `MERGE` `Source`
7. `MERGE` extracted entity nodes
8. `MERGE` document-to-entity relationships

## 11. Beginner-Friendly Cypher Queries

The notebook should end with simple queries.

Recommended query set:

### Query 1: list documents and sources

Goal:
- show the basic graph shape

### Query 2: which documents mention a given technology or concept

Goal:
- show how graph querying maps to extracted fields

### Query 3: which business topics appear across multiple sources

Goal:
- show cross-source structure

### Query 4: what entities are attached to one document

Goal:
- show the local neighborhood of a document node

These are easier for a beginner audience than more abstract traversals.

## 12. Two Reference Articles

These two articles are useful as background reading for the extraction task:

- [Opinion Mining — 8 Useful Tools More Than Sentiment Analysis](https://spotintelligence.com/2023/01/17/opinion-mining-sentiment-analysis/)
- [How To Implement Information Extraction Made Simple](https://spotintelligence.com/2023/10/10/information-extraction/)

They are supporting references, not implementation templates.

## 13. File Plan

After the plan is approved, implementation should likely be split into:

### 1. `prompts/graph-metadata-extractor.py`

Purpose:
- source-agnostic extraction prompt

### 2. `knowledge_extraction_neo4j_demo.py`

Purpose:
- cell-split Python file for notebook-style execution

Sections:
- config
- file loading
- Pydantic schema
- extraction
- writing processed markdown
- Neo4j Aura ingestion
- Cypher queries

### 3. `scripts/export_graph_extractions.py`

Purpose:
- batch extraction CLI for pre-talk runs
- write newline-delimited JSON with source path, frontmatter, and extracted graph payload
- provide a reloadable artifact for ad-hoc ingestion or notebook inspection

### 4. optional `cypher/demo_queries.cypher`

Purpose:
- keep reusable Cypher snippets separate
