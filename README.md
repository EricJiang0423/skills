# skills

[中文说明](README.zh.md)

A collection of AI coding-assistant skills targeting **Claude** and **Claude Code**.

## Repository Layout

```text
skills/
├── lecture-to-latex/                ← skill package
│   └── SKILL.md
├── notebooklm-lit-review/            ← skill package
│   └── SKILL.md
├── job-hunt-copilot/                 ← skill package
│   ├── SKILL.md
│   ├── resources/
│   │   └── project_template.md
│   └── docs/
│       └── README.md
├── .gitignore
├── LICENSE
├── README.md
└── README.zh.md
```

## Skills

| Skill | Description |
|---|---|
| [lecture-to-latex](lecture-to-latex/SKILL.md) | Convert lecture PDF slides to bilingual academic LaTeX notes |
| [notebooklm-lit-review](notebooklm-lit-review/SKILL.md) | Query a NotebookLM knowledge base for literature-grounded answers with Harvard citations |
| [job-hunt-copilot](job-hunt-copilot/SKILL.md) | Tailor resumes, reframe project narratives, generate pitch scripts, and run mock interviews for job applications |

## Usage

### Claude Code

Copy or symlink the skill directory into your project's `.claude/skills/` directory, then
invoke it in a conversation:

```
Use $lecture-to-latex to rebuild my lecture slides as academic bilingual LaTeX notes.
```

### Claude (API / claude.ai)

Open a skill's `SKILL.md`, paste its contents as a system prompt or at the start of your
conversation, then ask Claude to execute the task.

## License

MIT — see [LICENSE](LICENSE).
