# skills

[English README](README.md)

面向 **Claude** 和 **Claude Code** 的 AI 编程助手 skill 集合。

## 仓库结构

```text
skills/
├── lecture-to-latex/                ← skill 包
│   └── SKILL.md
├── trip-design/                     ← skill 包
│   └── SKILL.md
├── notebooklm-lit-review/            ← skill 包
│   └── SKILL.md
├── .gitignore
├── LICENSE
├── README.md
└── README.zh.md
```

## Skill 列表

| Skill | 说明 |
|---|---|
| [lecture-to-latex](lecture-to-latex/SKILL.md) | 将 lecture PDF 幻灯片重建为双语学术 LaTeX 讲义 |
| [trip-design](trip-design/SKILL.md) | 将旅行照片转化为自包含、有叙事感的 HTML 旅行日记 |
| [notebooklm-lit-review](notebooklm-lit-review/SKILL.md) | 查询 NotebookLM 知识库，获取带 Harvard 引用的文献支撑答案 |

## 使用方法

### Claude Code

将 skill 目录拷贝或软链接到你的项目 `.claude/skills/` 目录，然后在对话中调用：

```
Use $lecture-to-latex to rebuild my lecture slides as academic bilingual LaTeX notes.
Use $trip-design to turn my travel photos into a diary.
```

### Claude（API / claude.ai）

打开目标 skill 的 `SKILL.md`，将其内容粘贴为 system prompt 或对话开头，然后让 Claude 执行任务。

## License

MIT — 详见 [LICENSE](LICENSE)。
