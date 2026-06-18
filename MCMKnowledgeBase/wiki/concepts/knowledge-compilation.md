---
title: "Knowledge Compilation"
sources: ["raw/llm-wiki-idea.md"]
related: ["[[llm-wiki]]", "[[three-layer-architecture]]", "[[wiki-operations]]", "[[rag-vs-compilation]]"]
tags: ["knowledge-management", "llm", "compilation"]
last_compiled: 2026-05-27
---

# Knowledge Compilation

Knowledge compilation is the process by which an LLM reads raw source documents, extracts key information, and **integrates it into an existing structured knowledge base** — updating entity pages, revising topic summaries, noting contradictions, and maintaining cross-references.

## Compilation vs. retrieval

Traditional RAG systems retrieve relevant chunks at query time and synthesize answers on the fly. The LLM rediscovers knowledge from scratch on every question. Nothing accumulates.

Compilation is different: knowledge is **compiled once and then kept current**, not re-derived on every query. When a new source arrives, the LLM:

1. Reads it in full
2. Extracts key concepts, entities, and claims
3. Creates or updates wiki pages for each concept
4. Updates cross-references across all affected pages
5. Notes where new data contradicts old claims
6. Appends an entry to the log

A single source might touch 10-15 wiki pages.

## Why it works

The tedious part of knowledge base maintenance is bookkeeping: updating cross-references, keeping summaries current, maintaining consistency. Humans abandon wikis because the maintenance burden grows faster than the value. LLMs don't get bored, don't forget to update a cross-reference, and can touch many files in one pass. The cost of maintenance approaches zero.
