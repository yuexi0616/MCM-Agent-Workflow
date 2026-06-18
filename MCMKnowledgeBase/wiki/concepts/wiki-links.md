---
title: "Wiki-Links"
sources: ["raw/llm-wiki-idea.md"]
related: ["[[llm-wiki]]", "[[knowledge-compilation]]", "[[obsidian-integration]]"]
tags: ["convention", "linking", "navigation"]
last_compiled: 2026-05-27
---

# Wiki-Links

Wiki-links are `[[double-bracket]]` cross-references between pages in the [[llm-wiki]]. They are the primary mechanism for building an interlinked knowledge graph from flat markdown files.

## Convention

- Links use the target page's filename without extension: `[[knowledge-compilation]]`
- Filenames are lowercase-with-hyphens: `[[three-layer-architecture]]`
- The display text can differ from the filename: `[[memex|Vannevar Bush's Memex]]`
- First mention of a concept in a page gets the link; subsequent mentions optionally re-link

## Red links

A link to a page that doesn't yet exist (a "red link" in Obsidian) is not a bug — it's a signal. Red links indicate concepts worth exploring, questions worth answering, pages worth creating. During [[wiki-operations|lint]], red links are surfaced as opportunities.

## Graph structure

Because every page uses wiki-links to reference related concepts, the wiki forms a directed graph. [[obsidian-integration|Obsidian's graph view]] renders this visually, making it easy to see hubs, orphans, and clusters.
