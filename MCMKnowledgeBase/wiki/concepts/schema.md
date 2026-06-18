---
title: "Schema"
sources: ["raw/llm-wiki-idea.md"]
related: ["[[three-layer-architecture]]", "[[llm-wiki]]", "[[human-llm-collaboration]]"]
tags: ["configuration", "architecture"]
last_compiled: 2026-05-27
---

# Schema

The schema is the configuration document (CLAUDE.md, AGENTS.md, etc.) that defines how the [[llm-wiki]] is structured, what conventions it follows, and what workflows the LLM should execute.

## Purpose

Without a schema, the LLM is a generic chatbot — it may write wiki pages, but inconsistently. The schema is what makes the LLM a **disciplined wiki maintainer**. It encodes:

- Directory structure and file naming conventions
- Frontmatter format and required fields
- Wiki-link conventions
- Operational workflows (ingest, query, lint)
- Page writing guidelines
- INDEX.md and log.md formats

## Co-evolution

The schema is not static. The human and LLM co-evolve it over time as they figure out what works for their domain. If a convention proves awkward, update the schema. If a new workflow emerges, document it. The schema is the **contract** between human and LLM about how the wiki is maintained.

## Format

The schema is written in the native instruction format of the LLM agent being used — CLAUDE.md for Claude Code, AGENTS.md for Codex, etc. It lives in the project root and is loaded automatically at the start of every session.
