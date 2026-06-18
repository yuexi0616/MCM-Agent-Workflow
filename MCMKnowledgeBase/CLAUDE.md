# MCM Knowledge Base — Wiki Compiler Schema

## Architecture

Three immutable layers:

```
raw/        — Curated source documents. READ-ONLY to the LLM. Never modified.
wiki/       — LLM-generated markdown files. The LLM owns this entirely.
CLAUDE.md   — This file. The schema. Co-evolved with the user over time.
```

## Directory Structure

```
raw/                  — Source documents (articles, papers, notes, transcripts)
  assets/             — Downloaded images and attachments
wiki/
  concepts/           — One .md per key concept extracted from raw/
  entities/           — One .md per named entity (people, organizations, products, books)
  overviews/          — High-level synthesis pages spanning multiple sources
  INDEX.md            — Content-oriented catalog of all wiki pages
  log.md              — Append-only chronological record of operations
```

## Frontmatter Convention

Every wiki page starts with YAML frontmatter:

```yaml
---
title: "Concept Name"
sources: ["raw/filename.md"]
related: ["[[concept-a]]", "[[concept-b]]"]
tags: ["tag1", "tag2"]
last_compiled: 2026-05-27
---
```

- `title`: The concept name (sentence case, no wiki-link brackets)
- `sources`: List of raw/ files that contributed to this page
- `related`: List of [[wiki-links]] to other wiki pages
- `tags`: Lowercase tags for Dataview compatibility
- `last_compiled`: ISO date of last update from raw sources

## Wiki-Link Conventions

- Use `[[page-name]]` for all cross-references between wiki pages
- Link filenames are lowercase-with-hyphens: `[[knowledge-compilation]]`
- First mention of a concept in a page gets the link; subsequent mentions optionally re-link
- Red links (pages not yet created) are fine — they indicate concepts worth exploring

## Operations

### Ingest

When the user adds a new source to `raw/` and says "ingest" or "compile":

1. Read the new source file(s) in full
2. Identify all key concepts, entities, and claims
3. For each concept:
   - If a page exists in `wiki/concepts/`: update it with new information, note contradictions
   - If no page exists: create one with proper frontmatter
4. Create/update entity pages in `wiki/entities/` for named things
5. Update `wiki/INDEX.md` — add new pages, update summaries
6. Append an entry to `wiki/log.md` with format: `## [YYYY-MM-DD] ingest | Source Title`
7. Report what was changed: new pages, updated pages, contradictions found

Compilation scope: only process raw files modified since their last compilation (compare file mtime against `last_compiled` dates in frontmatter). Use `--since` flag or git diff if available.

### Query

When the user asks a question:

1. Read `wiki/INDEX.md` to find relevant pages
2. Read the relevant pages and synthesize an answer
3. Cite sources using `[[wiki-links]]`
4. Offer to file the answer as a new wiki page if it has lasting value

### Lint

When the user says "lint":

1. Scan for contradictions between pages (same claim, different conclusions)
2. Find orphan pages (no inbound links from other pages)
3. Identify red links (mentioned concepts with no page yet)
4. Check for stale pages (sources updated but page not recompiled)
5. Suggest new sources or questions to investigate
6. Report findings as a checklist

## INDEX.md Format

```markdown
# Wiki Index

## Concepts
- [[concept-name]] — One-line summary of what this page covers

## Entities
- [[entity-name]] — One-line summary

## Overviews
- [[overview-name]] — One-line summary
```

Updated on every ingest. Read first on every query.

## log.md Format

```markdown
# Wiki Log

## [2026-05-27] ingest | Source Title
- New pages: [[a]], [[b]], [[c]]
- Updated: [[d]], [[e]]
- Notes: contradiction found between X and Y on topic Z

## [2026-05-27] lint
- Found 3 orphan pages, 2 contradictions
```

Append-only. Each entry starts with `## [YYYY-MM-DD] operation | details`.

## Page Writing Guidelines

- Each concept page should be 2-6 paragraphs. Not an essay — a compiled summary.
- Lead with the clearest definition or claim from the sources
- When sources conflict, note it explicitly: "Source A claims X, while Source B claims Y"
- Every claim should be traceable to a source in the frontmatter
- Use bullet lists for enumerations, not for narrative
- Default language: Chinese for all terminal conversations with the user.

## Command Confirmation Rule

When proposing to execute a command that requires user approval (file modifications, git operations, installs, etc.):

1. Briefly describe what the command does in plain Chinese — one sentence, not a paragraph
2. Show the exact command(s) to be run
3. Wait for explicit confirmation before executing

**Example:**
> 将创建 3 个目录并写入 12 个 wiki 页面文件。执行以下命令：
> `mkdir -p wiki/concepts/ && ...`
> 是否继续？
