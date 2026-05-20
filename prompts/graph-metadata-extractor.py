GRAPH_METADATA_EXTRACTOR = """
# Graph Metadata Extractor

<prompt_objective>
Analyze one markdown document and extract conservative, graph-friendly metadata
from the document body only.
</prompt_objective>

<prompt_rules>
1. Use only the document body provided in the user message.
2. Do not use frontmatter fields such as title, source, author, or URL as a shortcut.
3. Be conservative:
- include only named technologies that are clearly referenced
- do not include generic terms such as AI, LLM, software, platform, or app
  unless they refer to a specific named technology
4. Empty arrays are valid.
5. Use commonly accepted names when possible.
6. Do not invent people, organizations, concepts, or business topics.
7. Keep the summary short and concrete.

Output MUST follow this exact structure:
{
  "summary": "2-4 sentence summary",
  "technologies": ["named technologies only"],
  "concepts": ["technical or domain concepts"],
  "business_topics": ["business-facing topics"],
  "people": ["named people"],
  "organizations": ["named organizations"]
}
</prompt_rules>

<output_requirements>
1. The summary must be 2-4 sentences.
2. All arrays must be flat arrays of strings.
3. Output should stay conservative rather than exhaustive speculation.
4. If an item is not explicitly supported by the document body, leave it out.
</output_requirements>
"""
