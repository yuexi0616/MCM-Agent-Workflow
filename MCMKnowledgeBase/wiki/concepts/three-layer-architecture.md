---
title: "Three-Layer Architecture"
sources: ["raw/llm-wiki-idea.md"]
related: ["[[llm-wiki]]", "[[knowledge-compilation]]", "[[schema]]", "[[wiki-operations]]"]
tags: ["architecture", "knowledge-management"]
last_compiled: 2026-05-27
---

# Three-Layer Architecture

The LLM Wiki pattern rests on three immutable layers that separate concerns between raw truth, compiled knowledge, and behavioral configuration.

## Layer 1: Raw sources

A curated collection of source documents — articles, papers, images, data files. These are **immutable**: the LLM reads from them but never modifies them. This is the source of truth. Everything in the wiki must be traceable back to a raw source.

## Layer 2: The wiki

A directory of LLM-generated markdown files: concept pages, entity pages, overviews, comparisons, a synthesis. The LLM **owns this layer entirely** — it creates pages, updates them when new sources arrive, maintains cross-references, and keeps everything consistent. The human reads it; the LLM writes it.

## Layer 3: The schema

A configuration document (CLAUDE.md, AGENTS.md, etc.) that tells the LLM how the wiki is structured, what the conventions are, and what workflows to follow. This is what makes the LLM a **disciplined wiki maintainer** rather than a generic chatbot. The human and LLM co-evolve the schema over time as they figure out what works for their domain.

## Design principle

The three layers are strictly separated. The LLM never writes to raw/. The human rarely writes to wiki/. The schema is the contract between them, and it evolves with experience.
