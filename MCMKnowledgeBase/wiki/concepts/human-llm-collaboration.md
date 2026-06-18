---
title: "Human-LLM Collaboration"
sources: ["raw/llm-wiki-idea.md"]
related: ["[[llm-wiki]]", "[[knowledge-compilation]]", "[[wiki-operations]]", "[[schema]]", "[[multi-agent-collaboration]]", "[[agent-role-specialization]]"]
tags: ["collaboration", "workflow", "human-in-the-loop"]
last_compiled: 2026-05-29
---

# Human-LLM Collaboration

The LLM Wiki pattern defines a clear division of labor between human and LLM in knowledge work.

## Human responsibilities

- **Curating sources**: Deciding what to read and add to `raw/`
- **Directing analysis**: Guiding the LLM on what to emphasize, what's important
- **Asking good questions**: Driving exploration and synthesis
- **Thinking about meaning**: The human does the actual understanding and sensemaking
- **Co-evolving the schema**: Refining conventions with the LLM over time

## LLM responsibilities

- **Reading and extracting**: Processing raw sources and identifying key concepts
- **Summarizing**: Writing concise, accurate summaries
- **Cross-referencing**: Maintaining [[wiki-links]] between related pages
- **Filing and bookkeeping**: Updating INDEX.md, log.md, and keeping pages consistent
- **Flagging contradictions**: Noting when new data conflicts with existing claims

## The Obsidian workflow

In practice, the human has the LLM agent open on one side and Obsidian open on the other. The LLM makes edits based on conversation; the human browses results in real time — following links, checking the graph view, reading updated pages. Obsidian is the IDE; the LLM is the programmer; the wiki is the codebase.

## Why this division works

The tedious parts of knowledge management (bookkeeping) go to the LLM. The valuable parts (curation, direction, thinking) stay with the human. Neither does the other's job well.

## Multi-Agent extension

This two-party (human + LLM) model can be extended to [[multi-agent-collaboration|multi-agent systems]] where multiple specialized LLM agents — modeler, coder, writer, auditor — collaborate through structured protocols. The [[agent-role-specialization|role specialization]] pattern and [[chain-intercept-workflow|chain-intercept workflow]] documented in the MCM Agent Workflow represent a concrete instantiation of this extension for mathematical modeling competitions.
