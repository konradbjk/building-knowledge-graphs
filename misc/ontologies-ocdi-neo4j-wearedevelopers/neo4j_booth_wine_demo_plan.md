# Neo4j Booth Wine Demo Execution Tracker

## Objective

Build a notebook demo, `ontologies-ocdi-neo4j-wearedevelopers.ipynb`, that shows Neo4j Aura as an aggregated metadata index over three wine-related datastores. The demo must route questions to the right datastore tools, retrieve top-1 text evidence from each selected store, and synthesize a short final answer.

## Fixed Constraints

- Notebook-first demo, easy to read live
- Based on [knowledge_extraction_neo4j.ipynb](/Users/konrad/Projects/building-knowledge-graphs/knowledge_extraction_neo4j.ipynb)
- Use `pydantic-ai` for inference and typed outputs
- Use `langgraph` for orchestration and parallel datastore calls
- Neo4j stores only aggregated datastore coverage and datastore overlap
- Neo4j does not store internal document nodes or chunk nodes
- Corpus lives in `data/winde_demo/`
- Corpus documents are English topical briefs
- Each brief uses `metadata:` frontmatter
- Each brief has 1000-2000 words of body text, excluding frontmatter
- `region` is metadata, not the document identity
- `vine_diseases` and `wine_diseases` use SQLite FTS
- `wine_making` has an optional Qdrant vector path with recursive chunking at 1000 characters and 200 overlap
- The Qdrant embedding/indexing cells exist in the notebook but are not part of the live booth run
- The final synthesis prompt consumes only retrieved text snippets

## Exact Deliverables

- [misc/ontologies-ocdi-neo4j-wearedevelopers/neo4j_booth_wine_demo_plan.md](/Users/konrad/Projects/building-knowledge-graphs/misc/ontologies-ocdi-neo4j-wearedevelopers/neo4j_booth_wine_demo_plan.md)
  Role: execution tracker with ordered tasks and validation gates
- `data/winde_demo/vine_diseases/*.md`
  Role: long vineyard-disease topical briefs with `metadata:` frontmatter
- `data/winde_demo/wine_diseases/*.md`
  Role: long wine-quality topical briefs with `metadata:` frontmatter
- `data/winde_demo/wine_making/*.md`
  Role: long cellar-process topical briefs with `metadata:` frontmatter
- `prompts/wine_demo_prompts.py`
  Role: extraction, triage, SQLite SQL translation, Qdrant query/filter generation, and final synthesis prompts
- `ontologies-ocdi-neo4j-wearedevelopers.ipynb`
  Role: main demo notebook with extraction, datastore build, Neo4j graph creation, LangGraph routing, and live questions
- `processed/winde_demo/*.jsonl`
  Role: incremental extraction checkpoints
- `processed/winde_demo/sqlite/*.db`
  Role: SQLite FTS datastores for `vine_diseases` and `wine_diseases`

## Ordered Checklist

- [x] Lock the shared wine-demo metadata schema and repository conventions.
  Validation: inspect the corpus and confirm every document uses the same frontmatter layout with `metadata`, `regions`, `varieties`, `diseases`, `winemaking_steps`, `quality_effects`, and `keywords`.

- [x] Finish `vine_diseases` as long topical briefs.
  Validation: inspect every file in `data/winde_demo/vine_diseases/` and confirm `metadata:` frontmatter, 1000-2000 body words, and no remaining `graph:` key.

- [x] Rewrite `wine_diseases` as long topical briefs.
  Validation: inspect every file in `data/winde_demo/wine_diseases/` and confirm `metadata:` frontmatter, 1000-2000 body words, and no remaining `graph:` key.

- [x] Rewrite `wine_making` as long topical briefs.
  Validation: inspect every file in `data/winde_demo/wine_making/` and confirm `metadata:` frontmatter, 1000-2000 body words, and no remaining `graph:` key.

- [x] Verify the final corpus inventory and word counts across all three repositories.
  Validation: run a repo-wide check over `data/winde_demo/` and confirm file counts, word counts, and zero `graph:` matches.

- [x] Replace the old prompt file with `prompts/wine_demo_prompts.py`.
  Validation: inspect the prompt file and confirm it contains separate prompts for metadata extraction, question triage, SQLite SQL translation, Qdrant query/filter generation, and final synthesis.

- [x] Mark the SQLite SQL translation prompt with schema and allowed datastore values.
  Validation: inspect the prompt text and confirm it explicitly instructs the model to use only the provided SQLite schema and allowed values for that datastore.

- [x] Remove runtime dependence on `prompts/winde_demo_prompts.py`.
  Validation: search the repo and confirm the new demo path only loads `prompts/wine_demo_prompts.py`.

- [x] Remove runtime dependence on `winde_demo_support.py`.
  Validation: search the repo and confirm the new demo path does not import or execute `winde_demo_support.py`.

- [x] Remove the old `graph_as_index_wine_demo.ipynb` from the active runtime path.
  Validation: search the repo and confirm the new demo flow points to `ontologies-ocdi-neo4j-wearedevelopers.ipynb` instead.

- [x] Build the SQLite storage schema for `vine_diseases`.
  Validation: create the SQLite database, inspect the schema, and execute a representative top-1 retrieval query successfully.

- [x] Build the SQLite storage schema for `wine_diseases`.
  Validation: create the SQLite database, inspect the schema, and execute a representative top-1 retrieval query successfully.

- [x] Implement the `pydantic-ai` SQL translation path for SQLite tools.
  Validation: inspect the notebook and confirm `sqlite_tool` builds a `pydantic-ai` agent with `render_sqlite_sql_prompt(...)`, `output_type=SqliteQueryPlan`, and `await agent.run(...)` before executing the returned SQL.

- [x] Run the live model-backed SQLite SQL translation validation.
  Validation: execute the translation step with real model credentials and confirm it returns one simple SQL query plus parameters for a single datastore.

- [x] Add the optional Qdrant chunking cell for `wine_making`.
  Validation: inspect the notebook and confirm recursive chunking is set to 1000 characters with 200 overlap.

- [x] Add per-chunk metadata extraction for the `wine_making` Qdrant path.
  Validation: inspect the notebook and confirm chunk metadata is extracted and preserved for payload storage.

- [x] Add the Qdrant embedding and upsert cells for `wine_making`.
  Validation: inspect the notebook and confirm embeddings creation and collection upsert logic exist in precompute-only cells.

- [x] Implement the `pydantic-ai` query-planning path for the `wine_making` Qdrant tool.
  Validation: inspect the notebook and confirm the query plan returns semantic query text plus structured filter fields for Qdrant payload filtering.

- [x] Add the Neo4j Aura connection and demo reset cells.
  Validation: inspect the notebook and confirm it includes a `demo_id`-scoped reset of the booth-demo subgraph.

- [x] Add datastore nodes and aggregated concept coverage edges to Neo4j.
  Validation: inspect the notebook and confirm it creates `DataStore` nodes plus aggregated `COVERS` links to `Region`, `Variety`, `Disease`, `Process`, `QualityEffect`, and `Keyword`.

- [x] Add Neo4j datastore overlap materialization.
  Validation: inspect the notebook and confirm it creates `OVERLAPS_WITH` edges with shared terms, shared types, and score properties.

- [x] Add manual Cypher cells for the booth demo.
  Validation: inspect the notebook and confirm it includes a coverage query and an overlap query that show what information is where and how datastores relate.

- [x] Add the `QuestionTriage` model and triage agent.
  Validation: inspect the notebook and confirm the triage step returns normalized regions, varieties, diseases, processes, quality effects, keywords, and requested outcome.

- [x] Add Neo4j-based routing from triage output to datastore selection.
  Validation: inspect the notebook and confirm the routing step returns datastore names and matched graph terms without requiring document nodes in Neo4j.

- [x] Add the SQLite datastore tools to the notebook runtime.
  Validation: inspect the notebook and confirm the SQLite tools execute their own translation and retrieval logic internally and return top-1 text results.

- [x] Add the Qdrant datastore tool to the notebook runtime.
  Validation: inspect the notebook and confirm the Qdrant tool executes its own query planning and returns one text chunk result.

- [x] Add the LangGraph state model and workflow graph.
  Validation: inspect the notebook and confirm the runtime graph is `triage_question -> route_with_neo4j -> retrieve_from_selected_datastores -> synthesize_answer`.

- [x] Add parallel datastore fan-out inside the LangGraph retrieval step.
  Validation: inspect the notebook and confirm selected datastore tools are called in parallel and their text outputs are merged into shared state.

- [x] Add the final answer synthesis step.
  Validation: inspect the notebook and confirm the final prompt consumes only retrieved text results and produces the final answer.

- [x] Add the three live demo questions to the notebook.
  Validation: inspect the notebook and confirm the first two questions route to one datastore and the third can route to two datastores.

- [x] Run the local validation loop for all paths that do not require external credentials.
  Validation: execute the local corpus, SQLite, and notebook-supporting code paths, fix failures, and keep iterating until the local demo path is stable.

- [x] Leave `ontologies-ocdi-neo4j-wearedevelopers.ipynb` ready for the final cell-by-cell run in your environment.
  Validation: confirm the notebook has the final section order, no active dependency on old demo files, and no unresolved local runtime errors in the validated paths.

## Demo Questions To Support

1. Which cultivars look safest for central Poland if fungal diseases are the main constraint?
2. What signs tell a French winery that gray rot is already hurting wine quality?
3. Gray rot affected Pinot Noir grapes in France. How can it change wine quality, and what cellar step helps reduce clarification or filtration problems?

## Current Status

- [x] Execution tracker rewritten
- [x] Shared metadata schema locked in code and corpus
- [x] `vine_diseases` complete
- [x] `wine_diseases` complete
- [x] `wine_making` complete
- [x] Corpus verification complete
- [x] Prompt layer replaced
- [x] Old runtime path removed
- [x] SQLite implementation complete
- [x] Live SQLite model validation complete
- [x] Qdrant tooling complete
- [x] Neo4j graph cells complete
- [x] LangGraph runtime complete
- [x] Local validation loop complete
- [x] Notebook ready for final run

Live validation completed:
- Azure OpenAI metadata extraction executed successfully from the notebook path
- Azure OpenAI SQLite SQL translation executed successfully from the notebook path
- Cohere `embed-v4.0` embedding generation executed successfully

Live validation still blocked by environment state:
- Neo4j Aura cannot be exercised yet because only `NEO4J_USERNAME` and `NEO4J_PASSWORD` are set; the notebook also requires `NEO4J_URI` or `NEO4J_INSTANCE_ID`
- Qdrant retrieval cannot be exercised yet because `http://localhost:6333` is refusing connections, so the local service or collection is not currently available
