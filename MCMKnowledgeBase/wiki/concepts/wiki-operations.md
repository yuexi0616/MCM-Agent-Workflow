---
title: "Wiki Operations"
sources: ["raw/llm-wiki-idea.md"]
related: ["[[llm-wiki]]", "[[knowledge-compilation]]", "[[wiki-indexing]]", "[[human-llm-collaboration]]", "[[chain-intercept-workflow]]"]
tags: ["workflow", "operations", "knowledge-management"]
last_compiled: 2026-05-29
---

# Wiki Operations

The LLM Wiki supports three core operations that define all interaction with the knowledge base.

## Ingest

The primary operation. The user drops a new source into `raw/` and tells the LLM to process it. Flow:

1. LLM reads the source in full
2. Discusses key takeaways with the user
3. Writes or updates concept and entity pages across the wiki
4. Updates [[wiki-indexing|INDEX.md]]
5. Appends an entry to [[wiki-indexing|log.md]]

A single source might touch 10-15 wiki pages. The user can stay involved (read summaries, guide emphasis) or batch-ingest many sources with less supervision.

## Query

The user asks questions against the compiled wiki. The LLM reads [[wiki-indexing|INDEX.md]] first to find relevant pages, then synthesizes an answer with citations. Answers can take multiple forms: markdown pages, comparison tables, Marp slide decks, matplotlib charts, canvases.

Critical insight: **good answers should be filed back into the wiki as new pages.** A comparison, an analysis, a discovered connection — these compound in the knowledge base rather than disappearing into chat history.

## Lint

Periodic health checks on the wiki. The LLM scans for:

- Contradictions between pages
- Stale claims superseded by newer sources
- Orphan pages with no inbound links
- Important concepts mentioned but lacking their own page (red links)
- Missing cross-references
- Data gaps that could be filled with web search

Lint keeps the wiki healthy as it grows and often surfaces new questions to investigate.

This ingest-then-lint rhythm mirrors the [[chain-intercept-workflow|chain-intercept workflow]] in multi-agent systems: build first, audit second, correct as needed.
