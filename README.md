# skills

[中文说明](README.zh.md)

A collection of AI coding-assistant skills targeting **Claude**, **Claude Code**, and **Codex**.

## Repository Layout

```text
skills/
├── lecture-to-latex/                ← skill package
│   └── SKILL.md                     ← universal skill specification
├── .gitignore
├── LICENSE
├── README.md
└── README.zh.md
```

## Skills

| Skill | Description |
|---|---|
| [lecture-to-latex](lecture-to-latex/SKILL.md) | Convert lecture PDF slides to bilingual academic LaTeX notes |

## Usage

### Claude Code

Copy or symlink `lecture-to-latex/` into your project's `.claude/skills/` directory, then
invoke the skill in a conversation:

```
Use $lecture-to-latex to rebuild my lecture slides as academic bilingual LaTeX notes.
```

### Claude (API / claude.ai)

Open [`lecture-to-latex/SKILL.md`](lecture-to-latex/SKILL.md), paste its contents as a
system prompt or at the start of your conversation, then ask Claude to convert your slides.

## License

MIT — see [LICENSE](LICENSE).
