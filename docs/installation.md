# 让技能生效

## 问题：Claude Code 不认识这个文件夹

Claude Code 只在固定的几个位置找技能：

| 位置 | 作用范围 |
|---|---|
| `~/.claude/skills/` | **个人技能，所有项目都能用**（最常用） |
| `<某个项目>/.claude/skills/` | 只在那一个项目里能用 |

放在别处的技能，**不建立关联就不会被触发**。

## 解决办法：符号链接

把技能实体放在一个你方便编辑的目录（比如本仓库），
再在 `~/.claude/skills/` 里建一个**符号链接**指过来。

```bash
ln -sfn "$PWD/find-literature" ~/.claude/skills/find-literature
ln -sfn "$PWD/pptx-animation" ~/.claude/skills/pptx-animation
```

```
~/.claude/skills/                        ← Claude Code 在这里找
├── find-literature -> <repo>/find-literature
└── pptx-animation  -> <repo>/pptx-animation
```

两个箭头是"快捷方式"。**你在仓库里改内容，改的就是正在生效的那份**，
不需要复制来复制去。

## 新建技能时要多做一步

复制 `templates/SKILL.md` 建好技能文件夹之后，还要建链接：

```bash
ln -s "$PWD/你的技能名" ~/.claude/skills/你的技能名
```

然后**开一个新的 Claude Code 会话**，技能才会被扫描到。

## 查看现在有哪些技能在生效

**最快的方法是在对话框里输入 `/skills`** —— 直接列出当前所有可用技能。
`/plugin stats` 还能看到每条技能占用了多少上下文。

从命令行查：

```bash
ls -la ~/.claude/skills/
```

列出名字后面带 `->` 的都是有效的链接。
如果某个技能本该出现却没出现，先跑这个命令看链接在不在、有没有指错地方。

## 名字的两条规矩

1. **你能输入的命令名 = 链接名**，不是目标文件夹的名字，也不是 frontmatter 里的 `name`。
   名字不合心意，改链接名就行（`ln -sfn` 重建）。
2. **`synced` 是保留目录名** —— `~/.claude/skills/` 下不能建叫 `synced` 的文件夹，
   会被跳过（那是给 claude.ai 同步功能留的）。

## 如果技能时灵时不灵：可能是"描述预算"被挤爆了

所有技能的 `description` 加起来有**总预算 ≈ 上下文的 1%（约 6000 字符）**，
Claude Code **自带的十几条技能也在这个池子里**。

超了就会全局截断，**某些技能的描述会变成只有名字**，AI 自然就想不起来用它。

排查：对话框输入 `/skills`，如果看到描述不完整，就是预算爆了。解决办法：

- 精简各条技能的 `description`
- 或者到 settings 里调大 `skillListingBudgetFraction`
- 或者关掉用不上的自带技能（`disableBundledSkills`）

单条 SKILL.md 文件本身还有 **1 MB** 上限，正常写不可能碰到。

## ⚠️ 移动仓库之后链接会静默失效

**链接里存的是绝对路径。** 一旦你把仓库目录改名或挪走，所有链接就都会失效——
而且是**静默失效**：不报错，技能就是不出现。

搬家之后要重建链接：

```bash
cd <新的仓库路径>
for name in find-literature pptx-animation; do
  ln -sfn "$PWD/$name" ~/.claude/skills/$name
done
```

## 检查链接有没有断

```bash
for l in ~/.claude/skills/*; do
  [ -e "$l" ] || echo "断了：$l"
done
```

没有输出就是全都正常。
