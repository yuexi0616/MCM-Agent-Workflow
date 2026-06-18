---
title: "Obsidian Integration"
sources: ["raw/llm-wiki-idea.md"]
related: ["[[llm-wiki]]", "[[human-llm-collaboration]]", "[[cli-tools]]"]
tags: ["tooling", "obsidian", "workflow"]
last_compiled: 2026-05-27
---

# Obsidian Integration

Obsidian is the recommended browser/IDE for the LLM Wiki. The wiki is just a directory of markdown files, and Obsidian renders them with [[wiki-links]], graph view, and plugin support.

## Key features

- **Graph view**: The best way to see the shape of the wiki — which pages are hubs, which are orphans, how concepts connect
- **Web Clipper**: Browser extension that converts web articles to markdown. Essential for quickly getting sources into `raw/`
- **Local image downloads**: Bind "Download attachments for current file" to a hotkey (e.g. Ctrl+Shift+D). After clipping, downloads all images to `raw/assets/`. Lets the LLM view images directly instead of relying on URLs that may break

## Recommended plugins

- **Marp**: Markdown-based slide deck format. Generate presentations directly from wiki content
- **Dataview**: Runs queries over YAML frontmatter. If the LLM adds tags, dates, and source counts to frontmatter, Dataview can generate dynamic tables, lists, and dashboards

## LLM-image workflow

LLMs can't natively read markdown with inline images in one pass. The workaround: have the LLM read the text first, then view some or all referenced images separately to gain additional context.

## Git integration

The wiki is just a git repo of markdown files. This gives version history, branching, and collaboration for free — every change is tracked, every state is recoverable.
