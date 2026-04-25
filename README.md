# skills

[中文说明](README.zh.md)

A collection of AI coding-assistant skills targeting **Claude**, **Claude Code**, and **Codex**.

## Repository Layout

```text
skills/
├── .claude/
│   └── skills/
│       └── slides-to-latex.md      ← Claude Code skill entry point
├── .codex/
│   └── skills.yaml                 ← Codex skill registry
├── slides-to-latex/                ← skill package
│   ├── SKILL.md                    ← universal skill specification
│   ├── agents/
│   │   ├── claude.md               ← Claude / Claude Code agent config
│   │   └── codex.yaml              ← Codex agent config
│   ├── references/
│   ├── scripts/
│   ├── tests/
│   └── requirements.txt
├── .gitignore
├── LICENSE
├── README.md
└── README.zh.md
```

## Skills

| Skill | Description |
|---|---|
| [slides-to-latex](slides-to-latex/SKILL.md) | Rebuild lecture slides (PDF/PPT/PPTX) as bilingual academic LaTeX notes |

## Installation

### Claude Code

Copy or symlink `.claude/skills/` into your project's `.claude/skills/` directory, then
invoke the skill in a conversation:

```
Use $slides-to-latex to rebuild my lecture slides as academic bilingual LaTeX notes.
```

### Codex

Install the skill into your local Codex skills directory:

```bash
pip install -r slides-to-latex/requirements.txt
python3 slides-to-latex/scripts/install_to_codex.py --overwrite
```

Then invoke it in Codex:

```
Use $slides-to-latex to rebuild my lecture slides as academic bilingual LaTeX notes.
```

### Claude (API / claude.ai)

Open [`slides-to-latex/SKILL.md`](slides-to-latex/SKILL.md), paste its contents as a
system prompt or at the start of your conversation, then ask Claude to convert your slides.

## License

MIT — see [LICENSE](LICENSE).
