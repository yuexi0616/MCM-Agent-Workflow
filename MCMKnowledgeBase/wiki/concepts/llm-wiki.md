---
title: "LLM Wiki"
sources: ["raw/llm-wiki-idea.md"]
related: ["[[knowledge-compilation]]", "[[three-layer-architecture]]", "[[human-llm-collaboration]]", "[[memex]]"]
tags: ["pattern", "knowledge-management", "llm"]
last_compiled: 2026-05-27
---

# LLM Wiki

The LLM Wiki is a pattern for building personal knowledge bases where an LLM agent **incrementally builds and maintains a persistent, structured wiki** from a curated collection of raw source documents.

## Core insight

Most LLM-document interactions follow the RAG pattern: upload files, retrieve chunks at query time, generate answers. The LLM rediscovers knowledge from scratch on every question — nothing accumulates.

The LLM Wiki inverts this: instead of retrieving from raw documents at query time, the LLM **compiles knowledge once and keeps it current**. It reads sources, extracts key information, and integrates it into an interlinked web of markdown pages. Cross-references are pre-built. Contradictions are pre-flagged. The synthesis reflects everything you've read.

## Key properties

- **Persistent and compounding**: The wiki gets richer with every source and every question. Good answers get filed back as new pages.
- **LLM-owned**: The human never (or rarely) writes the wiki. The LLM does all summarizing, cross-referencing, filing, and bookkeeping.
- **Human-directed**: The human curates sources, asks questions, guides analysis, and thinks about meaning. The LLM does everything else.

## Applicability

The pattern generalizes across domains: personal knowledge management, academic research, book companion wikis, business/team wikis, competitive analysis, due diligence, trip planning, course notes, and hobby deep-dives.

## Historical context

The idea descends from [[memex|Vannevar Bush's Memex]] (1945) — a personal, curated knowledge store with associative trails. Bush couldn't solve the maintenance problem. LLMs do.
