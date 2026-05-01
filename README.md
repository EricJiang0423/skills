# skills

[中文说明](README.zh.md)

A collection of AI coding-assistant skills targeting **Claude** and **Claude Code**.

## Repository Layout

```text
skills/
├── lecture-to-latex/                ← skill package
│   └── SKILL.md
├── trip-design/                     ← skill package
│   └── SKILL.md
├── .gitignore
├── LICENSE
├── README.md
└── README.zh.md
```

## Skills

| Skill | Description |
|---|---|
| [lecture-to-latex](lecture-to-latex/SKILL.md) | Convert lecture PDF slides to bilingual academic LaTeX notes |
| [trip-design](trip-design/SKILL.md) | Turn travel photos into self-contained, narrative-driven HTML travel diaries |

## Usage

### Claude Code

Copy or symlink the skill directory into your project's `.claude/skills/` directory, then
invoke it in a conversation:

```
Use $lecture-to-latex to rebuild my lecture slides as academic bilingual LaTeX notes.
Use $trip-design to turn my travel photos into a diary.
```

### Claude (API / claude.ai)

Open a skill's `SKILL.md`, paste its contents as a system prompt or at the start of your
conversation, then ask Claude to execute the task.

## License

MIT — see [LICENSE](LICENSE).
