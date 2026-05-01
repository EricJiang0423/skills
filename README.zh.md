# skills

[English README](README.md)

面向 **Claude**、**Claude Code** 和 **Codex** 的 AI 编程助手 skill 集合。

## 仓库结构

```text
skills/
├── lecture-to-latex/                ← skill 包
│   └── SKILL.md                     ← 通用 skill 规格说明
├── .gitignore
├── LICENSE
├── README.md
└── README.zh.md
```

## Skill 列表

| Skill | 说明 |
|---|---|
| [lecture-to-latex](lecture-to-latex/SKILL.md) | 将 lecture PDF 幻灯片重建为双语学术 LaTeX 讲义 |

## 使用方法

### Claude Code

将 `lecture-to-latex/` 拷贝或软链接到你的项目 `.claude/skills/` 目录，然后在对话中调用：

```
Use $lecture-to-latex to rebuild my lecture slides as academic bilingual LaTeX notes.
```

### Claude（API / claude.ai）

打开 [`lecture-to-latex/SKILL.md`](lecture-to-latex/SKILL.md)，将其内容粘贴为 system prompt 或对话开头，然后让 Claude 转换你的课件。

## License

MIT — 详见 [LICENSE](LICENSE)。
