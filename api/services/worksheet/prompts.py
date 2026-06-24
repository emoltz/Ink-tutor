"""Prompts for the worksheet skill-graph pipeline.

Highest-leverage thing to iterate on (see CLAUDE.md). The pipeline runs two
steps: DESCRIBE reads the page (vision), GRAPH structures it (text).
"""

DESCRIBE_PROMPT = """Look at this math worksheet. List the problems and the
specific techniques a student must USE to solve them on THIS page. Be concrete:
if many problems have variables on both sides, say so; if some require the
distributive property or combining like terms, name them. Do not list generic
curriculum topics the page doesn't actually require. Plain prose, no JSON."""

GRAPH_PROMPT = """Given this description of the skills a worksheet requires,
build a prerequisite skill graph. Return only JSON:
{"nodes":[{"id":"snake_case","label":"Skill","description":"short"}],"edges":[{"source":"prereq_id","target":"dependent_id"}]}

Rules:
- Include only skills the worksheet actually exercises (from the description).
- Build a real prerequisite chain, not a flat fan-in. Foundational skills (e.g.
  integer arithmetic) feed simplification skills (e.g. distributing, combining
  like terms), which feed the equation-solving moves, which feed the overall
  task. Most skills should depend on something other than the root.
- Edges point prerequisite -> dependent."""
