---
title: "Wiki Indexing"
sources: ["raw/llm-wiki-idea.md"]
related: ["[[wiki-operations]]", "[[llm-wiki]]", "[[knowledge-compilation]]"]
tags: ["indexing", "navigation", "knowledge-management"]
last_compiled: 2026-05-27
---

# Wiki Indexing

The LLM Wiki uses two special files for navigation, both distinct in purpose.

## INDEX.md — content-oriented catalog

A catalog of every page in the wiki, organized by category (concepts, entities, overviews). Each entry has a link and a one-line summary. The LLM updates it on every ingest and reads it first on every query to find relevant pages before drilling in.

At moderate scale (~100 sources, ~hundreds of pages), the index file alone is sufficient — no embedding-based RAG infrastructure needed.

## log.md — chronological record

An append-only timeline of everything that happened: ingests, queries, lint passes. Each entry starts with a parseable prefix:

```
## [2026-04-02] ingest | Article Title
## [2026-04-02] lint
## [2026-04-03] query | Topic of question
```

This format is deliberately grep-friendly: `grep "^## " log.md | tail -5` returns the last 5 operations. The log helps the LLM understand what's been done recently and gives the human a timeline of the wiki's evolution.

## Separation of concerns

INDEX.md answers "what's in the wiki?" (content-oriented). log.md answers "what happened and when?" (time-oriented). They serve different queries and are maintained independently.
