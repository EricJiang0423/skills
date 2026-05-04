# Job Hunt Copilot

求职全程助手 — 针对不同 JD 自动定制简历、重构项目叙事、生成面试讲稿、模拟面试。

## 安装

将整个目录复制或软链接到你的项目 `.claude/skills/` 下：

```bash
cp -r job-hunt-copilot /path/to/your-project/.claude/skills/
# 或
ln -s $(pwd)/job-hunt-copilot /path/to/your-project/.claude/skills/job-hunt-copilot
```

## 第一步：录入你的资料

Skill 被触发后会自动读取以下文件，你需要先填写它们：

```
job-hunt-copilot/
├── SKILL.md
└── resources/
    ├── self_profile.md       ← 填你的背景、技能、求职偏好
    ├── resume_base.md        ← 填你的全量简历母版
    ├── project_template.md   ← 项目录入模板（不需要改）
    └── projects/             ← 每个项目一个 .md 文件
```

你可以直接对 Claude 说：

- 「帮我填写 self_profile」— 口头描述你的背景，Claude 帮你整理
- 「我有个新项目要录入」— 触发项目录入流程
- 「把这份简历更新到 resume_base.md」— 上传现有简历，Claude 提取到母版

## 功能模块

| 模块 | 触发词 | 说明 |
|------|--------|------|
| 简历定制 | 「帮我针对这个 JD 改简历」 | 分析 JD 关键词，从项目库选材，定制 bullet points |
| 项目叙事重构 | 「从 XX 角度讲这个项目」 | 按产品/运营/研发/管理角度重新组织项目描述 |
| 面试讲稿生成 | 「帮我写项目介绍讲稿」 | 为每个选定项目生成双语 STAR 结构口述稿 |
| 项目录入 | 「我有个新项目要录入」 | 从原始素材中提取并填写项目模板 |
| 模拟面试 | 「帮我模拟面试」 | 行为面试 / JD 面试 / 综合，支持友好复盘和高压追问模式 |
| LaTeX 简历生成 | 「导出 LaTeX 简历」 | 生成 .tex 源文件，支持标准/学术/中文/软技能四种变体 |
| 论文转项目 | 「把这篇论文转成项目」 | 从学术论文中提取问题-方法-结果，转化为简历项目 |

## 输出格式

- 默认输出 `.tex`（LaTeX 源文件，可编译为 PDF）
- 也可输出 `.docx`（需 docx skill）
- 面试讲稿始终双语输出（中文 + 英文）


## 鸣谢

- Skill 框架基于 [spontaneousai/job-hunt-copilot](https://github.com/spontaneousai/job-hunt-copilot)
- LaTeX 简历模板作者：Jake Gutierrez（基于 [sb2nov/resume](https://github.com/sb2nov/resume)），MIT License
