# MCM Mathematical Contest in Modeling — Multi-Agent Collaboration System

A **4-Agent Chain-Intercept Collaboration System** for the MCM/ICM mathematical modeling competition, enabling end-to-end automation from problem analysis, mathematical modeling, and algorithm implementation to paper writing.

## Highlights

- **Chain-Intercept Workflow**: Modeler → Devil's Advocate (audit) → Coder → Devil's Advocate (audit) → Paper Writer → Devil's Advocate (final audit)
- **Result Authenticity Guarantee**: All numerical results must be computed by model formulas — zero tolerance for fabricated data
- **Structured Knowledge Base**: 54+ concept pages, 22 entity pages, covering CUMCM/MCM problems from 2022–2025
- **Continuous Improvement Loop**: 14-category error taxonomy with cross-run self-evolution
- **Resume-from-Checkpoint**: Recover execution from any interrupted phase

## System Architecture

### 4 Specialized Agents

| Agent | Role | Responsibility |
|-------|------|----------------|
| Modeler | Chief Modeling Scientist | Problem decomposition, assumption formulation, mathematical model design |
| Coder | Algorithm Engineer | Model implementation, numerical computation, visualization |
| Paper Writer | Editor-in-Chief | Paper drafting, formatting, AI-trace removal |
| Devil's Advocate | Independent Auditor | Cross-phase auditing, flaw detection, quality assurance |

### Pipeline Protocol

```
Phase 0: Data Extraction (problem parameter extraction)
    ↓
Phase 1: Model Design → Devil's Advocate Audit
    ↓
Phase 2: Code Implementation → Devil's Advocate Audit
    ↓
Phase 3: Paper Assembly → Devil's Advocate Audit
    ↓
Phase 4: Final Packaging (MD/DOCX/PDF + figures + results)
```

## Quick Start

### Bootstrap a New Problem

```bash
python tools/scaffold.py --problem "2025 MCM Problem A" --year 2025 --letter A
```

### Resume from Checkpoint

```bash
# View current status
python tools/run_mcm_gates.py --resume --status

# Resume from the interrupted phase
python tools/run_mcm_gates.py --resume
```

### One-Click Packaging

```bash
python tools/package_run.py --run _workspace/run-{timestamp}
```

## Directory Structure

```
MCM/
├── .claude/agents/          # Agent definition files
│   ├── modeling-expert.md
│   ├── coding-expert.md
│   ├── paper-writer.md
│   └── devils-advocate.md
├── MCMKnowledgeBase/        # Obsidian knowledge base
│   ├── wiki/                # Concept pages, entity pages, yearly overviews
│   └── raw/                 # Problem PDFs, attachments, OCR'd winning papers
│   └── Python reference code for 30 common models/
├── tools/                   # Utility scripts
│   ├── scaffold.py          # Problem scaffolding
│   ├── run_mcm_gates.py     # Quality gates + resume
│   └── package_run.py       # One-click packaging
├── _workspace/              # Runtime workspace
│   ├── input/               # Problem input
│   ├── phase-1-model.xml    # Modeling output
│   ├── phase-2-code.xml     # Code output
│   ├── phase-3-paper.md     # Paper output
│   └── run-{timestamp}/     # Final deliverables
└── docs/                    # Documentation
```

## Knowledge Base

`MCMKnowledgeBase/` is an Obsidian vault containing:

- **54+ Concept Pages**: Algorithm codebase, LaTeX reference, error taxonomy, etc.
- **22 Entity Pages**: Winning papers, problem entities, modeling experts, etc.
- **5 Yearly Overviews**: 2022–2025 CUMCM/MCM problem style and difficulty analysis

### Retrieval Protocol

1. Entry point: `MCMKnowledgeBase/wiki/INDEX.md`
2. Problem lookup: `wiki/entities/{year}-{letter}-{slug}.md`
3. Algorithm lookup: `wiki/concepts/{algorithm-name}.md`

## Quality Assurance

### Devil's Advocate Auditing

Each phase is independently audited upon completion:

- **Phase 1**: Assumption plausibility, mathematical rigor, dimensional consistency
- **Phase 2**: Code logic correctness, result authenticity (zero tolerance), visualization standards
- **Phase 3**: Competition compliance, cross-agent consistency, AIGC detection

### Retry & Error Handling

- Model revision: up to 5 rejections; after 5 consecutive rejections, redesign from scratch
- Code revision: up to 3 attempts
- Modeling feedback loop: when code is correct but results are anomalous, the model may be rejected for redesign (up to 3 times)

### Continuous Improvement

After each audit, errors are classified into 14 standard categories and written to `error-registry.json`. Agents perform pre-flight self-checks on startup, enabling cross-run self-evolution.

## Tech Stack

- Python 3.x
- Obsidian (knowledge base management)
- Pandoc (paper format conversion)
- Matplotlib (visualization)

## License

MIT License

## References

- [MCM/ICM Official Site](https://www.mcm-icm.org/)
- [CUMCM Official Site](http://www.cumcm.org.cn/)
