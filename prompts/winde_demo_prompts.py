DOCUMENT_EXTRACTOR_PROMPT = """
# Wine Demo Document Extractor

Extract graph-friendly metadata from one markdown document body about vineyards, wine quality, or winemaking.

Rules:
1. Use only the document body passed in the user message.
2. Stay conservative. If a region, variety, disease, or process is not clearly supported by the body, leave it out.
3. `keywords` must be practical routing phrases for the graph.
4. Do not use datastore names such as vine_diseases, wine_diseases, or wine_making as keywords.
5. Prefer specific domain phrases such as gray rot, gluconic acid, Pinot Noir, clarification, filtration, central Poland, or resistant cultivars.

Return this exact structure:
{
  "summary": "2-3 sentence summary",
  "regions": ["country or wine region names"],
  "varieties": ["grape variety names"],
  "diseases": ["vine or wine disease names"],
  "winemaking_steps": ["cellar process names"],
  "quality_effects": ["quality effects, markers, or sensory outcomes"],
  "keywords": ["3-8 routing keywords"]
}
"""


QUESTION_TRIAGE_PROMPT = """
# Wine Demo Question Triage

Analyze one user question for a graph-routed wine demo.

Rules:
1. Extract only the domain terms that are useful for routing and retrieval.
2. `routing_terms` should contain 3-6 concrete phrases that a graph can match to regions, varieties, diseases, quality effects, or cellar processes.
3. Do not use datastore names in `routing_terms`.
4. Prefer exact domain language from the question such as central Poland, gray rot, Pinot Noir, clarification, filtration, noble rot, resistant cultivars, or gluconic acid.

Return this exact structure:
{
  "question_type": "vineyard|wine_quality|winemaking|mixed",
  "regions": ["region names"],
  "varieties": ["grape varieties"],
  "diseases": ["diseases"],
  "winemaking_steps": ["cellar steps"],
  "quality_effects": ["quality effects or analytical markers"],
  "routing_terms": ["3-6 graph routing terms"]
}
"""


STORE_QUERY_PROMPT = """
# Wine Demo Store Query Rewriter

You are writing search keywords for one SQLite FTS repository.

Rules:
1. The repository description tells you what kind of material it contains.
2. Return short keyword phrases, not full sentences.
3. Prefer phrases that are likely to appear literally in documents.
4. Keep the list short: 3-6 keywords.
5. Do not include datastore names.

Return this exact structure:
{
  "keywords": ["3-6 search keywords"],
  "reason": "one short sentence"
}
"""


FINAL_ANSWER_PROMPT = """
# Wine Demo Answer Synthesizer

Answer the user using only the retrieved context from the selected repositories.

Rules:
1. Combine evidence across repositories when more than one repository was queried.
2. Stay short and concrete.
3. If the context is partial, say what is missing instead of inventing.
4. Mention the most relevant disease, quality effect, or cellar step directly.

Return this exact structure:
{
  "answer": "2-4 sentence answer grounded in the retrieved context"
}
"""
