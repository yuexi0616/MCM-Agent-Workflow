---
title: "CLI Tools"
sources: ["raw/llm-wiki-idea.md"]
related: ["[[llm-wiki]]", "[[obsidian-integration]]", "[[wiki-indexing]]"]
tags: ["tooling", "search", "cli"]
last_compiled: 2026-05-27
---

# CLI Tools

As the [[llm-wiki]] grows beyond what a simple [[wiki-indexing|INDEX.md]] can efficiently serve, CLI tools can help the LLM search, navigate, and operate on the wiki programmatically.

## Search engines

At small scale (~hundreds of pages), the index file is sufficient. As the wiki grows, proper search becomes valuable.

**qmd** is a local search engine for markdown files with hybrid BM25/vector search and LLM re-ranking, all on-device. It has both a CLI (the LLM can shell out to it) and an MCP server (the LLM can use it as a native tool).

## Custom tools

The LLM can help build simpler tools as needs arise — a naive search script, a dead-link checker, a frontmatter validator. The point is not to build infrastructure upfront but to add tools when the manual approach becomes painful.

## Design principle

Tools are optional and modular. Don't build them until the index file stops being enough. Let actual friction drive tooling decisions rather than anticipated scale.
