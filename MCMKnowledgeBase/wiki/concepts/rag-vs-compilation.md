---
title: "RAG vs Compilation"
sources: ["raw/llm-wiki-idea.md"]
related: ["[[knowledge-compilation]]", "[[llm-wiki]]"]
tags: ["comparison", "rag", "knowledge-management"]
last_compiled: 2026-05-27
---

# RAG vs Compilation

RAG (Retrieval-Augmented Generation) and [[knowledge-compilation]] represent two fundamentally different approaches to using LLMs with documents.

## RAG approach

Upload documents → index chunks → at query time, retrieve relevant chunks → generate answer.

The LLM rediscovers knowledge from scratch on every question. There is no accumulation. A subtle question requiring synthesis across five documents forces the LLM to find and piece together fragments every time. NotebookLM, ChatGPT file uploads, and most enterprise RAG systems work this way.

## Compilation approach

Read sources once → extract concepts → integrate into persistent [[llm-wiki|wiki]] → answer queries from pre-compiled knowledge.

Cross-references are already built. Contradictions are already flagged. The synthesis already reflects everything that's been read. The wiki compounds with every source and every question.

## When to use each

RAG is better for: ephemeral document collections, one-off questions, situations where the document set changes constantly and recompilation would be too expensive.

Compilation is better for: cumulative knowledge work, deep research over time, domains where connections between sources matter more than any single source, and situations where the human wants to build understanding progressively.
