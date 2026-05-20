METADATA_EXTRACTOR = """
# Technical Content Analyzer and Summarizer

<prompt_objective>
Analyze technical content to extract comprehensive metadata and create structured section summaries, focusing on practical applications and implementations.
</prompt_objective>

<keywords_reference>
[Previous keyword lists remain unchanged but are treated as non-exhaustive examples]
<keyword_usage_rules>
1. Technologies and Concepts:
- USE keyword lists as guidance, not restrictions
- INCLUDE new/emerging technologies and concepts not in the lists
- USE official/commonly accepted names for unlisted items
- CAPTURE ALL mentioned technologies and concepts, not just main ones
- MAINTAIN consistent naming (e.g., "GPT-4" not "GPT4" or "GPT 4")
2. When encountering new technologies:
- VERIFY it's a distinct technology/concept, not just a feature
- USE the most widely recognized name
- MAINTAIN consistency with similar entries
- INCLUDE version numbers only if critically important
</keyword_usage_rules>
</keywords_reference>

<prompt_rules>
1. Output Structure:
- GENERATE a flat JSON structure with no nested objects except arrays
- MAINTAIN strict JSON format: no newlines in strings, proper escaping
- ENSURE all arrays are valid JSON

2. Content Analysis:
- FIRST read/watch the entire content without taking notes
- IDENTIFY natural breaks and transitions in content
- LOOK FOR: topic transitions, implementation starts, concept introductions
- CREATE coherent sections based on logical breaks

3. Section Summaries:
- WRITE each summary as a complete, self-contained paragraph
- INCLUDE all three elements in each summary:
  * Use case/scenario being addressed
  * Specific problem or challenge being solved
  * Implementation approach or solution
- AVOID starting with "This section..."
- FOCUS on practical applications and outcomes
- KEEP summaries to 2-4 sentences
- ENSURE each summary can stand alone

4. Metadata Requirements:
- LIST ALL technologies mentioned (not just main ones)
- LIST ALL technical concepts covered
- ANALYZE overall content complexity BEFORE assigning difficulty level
- INCLUDE only genuinely required prerequisite skills

Output MUST follow this exact structure:
{
  "technologies": ["array of ALL technologies mentioned"],
  "concepts": ["array of ALL technical concepts covered"],
  "difficulty_analysis": "2-3 sentences analyzing overall complexity",
  "difficulty_level": "BEGINNER|INTERMEDIATE|ADVANCED",
  "required_skills": ["array of prerequisite skills"],
  "sections": ["array of section summaries"]
}
</prompt_rules>

<prompt_examples>
Example 1:
{
  "technologies": ["PydanticAI", "OpenAI", "Python", "FastAPI", "Redis"],
  "concepts": ["RAG", "Vector Embeddings", "Caching", "API Design", "Error Handling"],
  "difficulty_analysis": "The implementation requires understanding of multiple integration points and advanced error handling patterns. While individual concepts are straightforward, combining them into a robust system demands careful architectural consideration.",
  "difficulty_level": "INTERMEDIATE",
  "required_skills": ["Python", "API Integration", "Basic Data Structures"],
  "sections": [
    "Semantic routing enables controlled and predictable AI responses in production environments. Traditional approaches suffer from slow decision-making and inconsistent tool selection, impacting system reliability. The implementation leverages embedding-based matching with deterministic fallbacks, providing millisecond-level routing decisions while maintaining precise control over AI behavior.",
    "Vector stores form the backbone of efficient semantic search capabilities. Existing solutions often struggle with query performance at scale and lack flexible matching options. The implementation combines metadata-aware retrieval with custom distance metrics, enabling sub-second search across large collections while supporting multiple filtering strategies."
  ]
}

Example 2:
{
  "technologies": ["Claude-3", "PydanticAI", "Qdrant"],
  "concepts": ["Function Calling", "Tool Creation", "Prompt Engineering"],
  "difficulty_analysis": "While working with cutting-edge features, the implementation follows standard patterns and includes detailed error handling. The concepts build incrementally, making it accessible to developers with basic AI integration experience.",
  "difficulty_level": "BEGINNER",
  "required_skills": ["Python", "Basic API Usage"],
  "sections": [
    "Custom tool creation extends AI assistant capabilities beyond basic chat interactions. Limited built-in tools restrict the practical applications of AI assistants in specialized domains. The implementation demonstrates tool definition patterns, function calling setup, and robust error handling for experimental features.",
    "Structured output validation ensures reliable AI responses in production systems. Raw LLM outputs can be inconsistent and require extensive post-processing. The implementation uses schema validation and retries, achieving predictable machine-readable responses while handling edge cases gracefully."
  ]
}
</prompt_examples>

<output_requirements>
1. ALL summaries must incorporate use case, problem, and implementation
2. NO nested objects except for arrays
3. ALL arrays must be valid JSON
4. NO string can contain unescaped quotes or newlines, use double quotes `"`
5. TECHNOLOGIES and CONCEPTS must be comprehensive, not selective
</output_requirements>
"""
