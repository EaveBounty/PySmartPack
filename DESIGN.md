---
version: alpha
name: PySmartPack-design
inspiration: linear.app
description: >
  Dark, dense, developer-tool aesthetic for the PySmartPack desktop app.
  Near-black canvas (#0E0E11), four-step surface ladder, hairline borders,
  a single lavender-blue accent (#5E6AD2) reserved for focus / primary CTA /
  active state. No second chromatic accent. Maps Linear's web tokens onto a
  PySide6 + qfluentwidgets (Fluent Design) native window.
---

<!-- LANG-SWITCH --> **中文** · [English](./DESIGN_EN.md)  ·  📖 [README](./README.md)（[English](./README_EN.md)）

# PySmartPack 设计规范（DESIGN.md）

视觉的**唯一真源**。UI 层（`src/pysmartpack/ui/theme.py`）的 QSS 与 qfluentwidgets
主题色均派生自这些令牌。**不要在控件里硬编码颜色**，请从 `theme.Tokens` 取值。

> 上方 YAML front matter 为机器可读令牌（中英版本一致），供 getdesign.md 等工具消费；以下为中文说明，英文见 [DESIGN_EN.md](./DESIGN_EN.md)。

## 颜色令牌（对应 theme.py 的 Tokens.*）

| 令牌 | 色值 | 用途 |
|---|---|---|
| primary | `#5E6AD2` | 强调色：主按钮、激活标签、进度填充、焦点环 |
| primary_hover | `#828FFF` | primary 悬停态 |
| primary_pressed | `#5E69D1` | 按下 / 焦点着色 |
| on_primary | `#FFFFFF` | primary 上的文字 |
| canvas | `#0E0E11` | 窗口背景（比 Linear #010102 略提亮，桌面更舒适） |
| surface_1 | `#16171A` | 卡片、面板、树、日志 |
| surface_2 | `#1C1D21` | 悬停/选中行、强调面板 |
| surface_3 | `#222329` | 菜单、弹出层、输入框 |
| hairline | `#2A2C32` | 1px 边框、分隔线 |
| hairline_strong | `#3A3B42` | 输入框边框 / 焦点基线 |
| ink | `#F7F8F8` | 主要文字、标题 |
| ink_muted | `#D0D6E0` | 次要文字 |
| ink_subtle | `#8A8F98` | 三级文字、说明、禁用标签 |
| ink_tertiary | `#62666D` | 脚注、占位符 |
| success | `#27A644` | 成功态（打包完成） |
| warning | `#E2A53B` | 警告（动态导入、缺依赖） |
| danger | `#E5484D` | 错误 / 失败 |

无障碍：canvas/surface 上的正文文字满足 WCAG AA（≥ 4.5:1）。**永不只用颜色**表达状态——
始终配合图标或文字标签（成功/警告/错误）。

## 字体

- UI 无衬线：`Segoe UI`（Windows 默认）→ `Inter` → 系统回退。
- 等宽（日志/代码/命令）：`Cascadia Code` → `JetBrains Mono` → `Consolas` → monospace。

| 角色 | 字号 | 字重 |
|---|---|---|
| title | 20px | 600 |
| section | 14px | 600（大写小标题，+0.4px 字距） |
| body | 14px | 400 |
| body-sm | 12px | 400 |
| button | 14px | 500 |
| mono | 13px | 400 |

## 形状与间距

- 基础间距单位：4px。梯度：4 / 8 / 12 / 16 / 24 / 32。
- 圆角：控件 6px，卡片 10px，胶囊 9999px。
- 卡片：`surface_1` 填充 + 1px `hairline` 边框，无投影（层级靠 surface 阶梯表达）。
- 焦点环：输入/聚焦控件上 1px `primary` 边框。

## 控件映射（qfluentwidgets）

- 窗口：`FluentWindow` / `MSFluentWindow`，深色主题，强调色 = `primary`。
- 主操作：`PrimaryPushButton`（打包 / Package）。
- 次操作：`PushButton`（浏览 / 分析）。
- 扫描结果：`surface_1` 上的 `TreeWidget`，可勾选项、类型图标。
- 选项：`CardWidget` 内的 `RadioButton` 组 + `SwitchButton` + `ComboBox`。
- 进度：`ProgressBar`（扫描时不确定态，打包时确定态）。
- 日志：只读 `TextEdit`（等宽），按级别着色（info/warn/error）。
- 提示：`InfoBar` 用于成功/错误反馈。

## 该做 / 不该做

- 该：lavender 仅保留给焦点 / 主 CTA / 激活态。
- 该：每个自动识别项都显示为可编辑、可勾选的行（不静默决策）。
- 不该：使用浅色营销风；默认深色发布（浅色作为可选切换）。
- 不该：引入第二种亮色强调色。
