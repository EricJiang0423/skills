# skills

[English README](README.md)

面向 **Claude**、**Claude Code** 和 **Codex** 的 AI 编程助手 skill 集合。

## 仓库结构

```text
skills/
├── .claude/
│   └── skills/
│       └── slides-to-latex.md      ← Claude Code skill 入口
├── .codex/
│   └── skills.yaml                 ← Codex skill 注册表
├── slides-to-latex/                ← skill 包
│   ├── SKILL.md                    ← 通用 skill 规格说明
│   ├── agents/
│   │   ├── claude.md               ← Claude / Claude Code agent 配置
│   │   └── codex.yaml              ← Codex agent 配置
│   ├── references/
│   ├── scripts/
│   ├── tests/
│   └── requirements.txt
├── .gitignore
├── LICENSE
├── README.md
└── README.zh.md
```

## Skill 列表

| Skill | 说明 |
|---|---|
| [slides-to-latex](slides-to-latex/SKILL.md) | 将 lecture slides（PDF/PPT/PPTX）重建为双语学术 LaTeX 讲义 |

## 安装使用

### Claude Code

将 `.claude/skills/` 拷贝或软链接到你的项目 `.claude/skills/` 目录，然后在对话中调用：

```
Use $slides-to-latex to rebuild my lecture slides as academic bilingual LaTeX notes.
```

### Codex

将 skill 安装到本地 Codex skills 目录：

```bash
pip install -r slides-to-latex/requirements.txt
python3 slides-to-latex/scripts/install_to_codex.py --overwrite
```

然后在 Codex 中调用：

```
Use $slides-to-latex to rebuild my lecture slides as academic bilingual LaTeX notes.
```

### Claude（API / claude.ai）

打开 [`slides-to-latex/SKILL.md`](slides-to-latex/SKILL.md)，将其内容粘贴为 system prompt 或对话开头，然后让 Claude 转换你的课件。

## License

MIT — 详见 [LICENSE](LICENSE)。
