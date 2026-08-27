---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# 第7章 前端开发概况与工程化演进

> **本章学习目标**
> - 能够用“职责与产物”说清前端在“浏览器—接口—存储”链路中的位置，并对比后端模板渲染与前后端分离两种形态的边界与代价
> - 能够客观对比 React / Vue / Angular 三者的设计哲学、数据流与适用场景，并在给定约束下给出不偏袒的选型判断
> - 能够解释 Vue 3 组合式 API 与 Proxy 响应式的基本原理，并说明 Vite 为何在开发期比传统打包器更快
> - 能够说清 Node.js、npm/pnpm、ES Module 三件套在前端工程化中的各自角色，并用 `package.json` 的依赖与脚本字段描述一个可复现的前端工程
> - 能够在无需掌握前端专家的前提下，以后端视角读懂前端目录、接口契约与构建产物，并完成与后端 API 的有效协作

> **为什么需要掌握本章**
> 会写后端接口，不等于能把产品交付到用户眼前。MeetingToText 的真实链路是“浏览器上传音频 → 后端转写 → 前端拉取并渲染任务列表与纪要”——前端负责把接口变为可交互的界面，把状态变为可观察的视图，把构建变为可部署的静态资源。若分不清“谁该渲染 HTML”“接口契约何时确定”“前端为何需要自己的包管理与构建”，后端开发者就会在联调时反复争执“这个字段到底谁来拼”“这个页面为何请求了三次”。本章是第三篇的起点：先用后端视角把前端的版图、选型与工程基石讲透，让你在后续的 Vue 3、路由与状态管理章节中，能以“协作方”而非“旁观者”参与前后端对话。

> **预计理论学时**：3学时

本章延续“先动机、后定义、再可运行示例”的节奏：每一节先讲清工程痛点，再给出最小可用定义，最后用一段可在本机复现的 `{code-cell}` 把概念固定下来。与第 1 至 6 章相同，所有示例均在书仓根目录的 `.venv` 环境中用标准库本地验证，无需启动真实的 ASR 模型、LLM 网络调用或前端 dev server。

章内结构如下：

- [7.1 前端在架构中的角色](7.1_frontend_role_in_architecture.md) —— 后端模板渲染 vs 前后端分离：职责如何切、URL 与数据如何分工、MeetingToText 如何落地
- [7.2 框架三驾马车](7.2_framework_troika.md) —— React / Vue / Angular 设计哲学客观对比：声明式、响应式与企业级约束的 trade-off
- [7.3 为何选择 Vue 3 + Vite](7.3_why_vue3_vite.md) —— 组合式 API、Proxy 响应式与构建速度：本课程前端栈的选型依据
- [7.4 前端工程化基石](7.4_frontend_engineering_foundation.md) —— Node.js、npm/pnpm、ES Module：前端如何拥有自己的“运行时 + 包管理 + 模块系统”

此外，本章所有可执行示例均可在书仓 `.venv` 环境中复现；涉及 MeetingToText 的片段复用 `m2t` 教学包，前端契约以通用内联示例呈现（如 `fetch('/mock.json')` 与 `v-for` 渲染的最小闭环），无需启动真实服务。

> **环境约定**：本书面向 Linux，本章命令均面向 Linux，路径与环境激活统一使用 `source .venv/bin/activate` 与 `/` 分隔符；正文跨章引用一律使用相对链接，如 [第1章 开发者的元技能](../../part1_software_engineering/chapter01_dev_meta_skills/index.md) 与 [第3章 后端开发到底是什么](../../part2_backend_development/chapter03_backend_essence/index.md)。

文件 `book/part3_frontend_collaboration/chapter07_frontend_overview/demo_index.py`（验证本章环境与前后端协作概念可用）：

```{code-cell} ipython3
# 文件 book/part3_frontend_collaboration/chapter07_frontend_overview/demo_index.py
import sys, pathlib, json

import m2t
from m2t.store import TaskStore

print("m2t version:", m2t.__version__)
print("python:", sys.version.split()[0])
print("TaskStore:", TaskStore.__name__)

# 前端视角的最小契约：后端返回的任务列表，前端用 v-for 渲染
sample_tasks = [
    {"id": "1", "filename": "meeting.wav", "status": "done"},
    {"id": "2", "filename": "interview.mp3", "status": "processing"},
]
# 模拟前端对接：把后端 JSON 直接映射为 UI 文案（不依赖真实前端构建）
for t in sample_tasks:
    label = f"{t['filename']} — {t['status']}"
    print(label)

# 前端工程契约：用 Python 解析内联 package.json（工程化协作点）
pkg = {
    "name": "frontend-min",
    "type": "module",
    "dependencies": {"vue": "^3.4.0"},
    "devDependencies": {"vite": "^5.0.0", "vue-tsc": "^2.0.0"},
    "scripts": {"dev": "vite", "build": "vue-tsc -b && vite build", "preview": "vite preview"},
}
print("frontend deps:", list(pkg.get("dependencies", {}).keys()))
print("frontend scripts:", list(pkg.get("scripts", {}).keys()))

print("prefix:", pathlib.Path(sys.prefix).name)
# 预期输出:
# m2t version: 0.1.0
# python: 3.12.x
# TaskStore: TaskStore
# meeting.wav — done
# interview.mp3 — processing
# frontend deps: ['vue']
# frontend scripts: ['dev', 'build', 'preview']
# prefix: .venv 或系统前缀
```

```bash
# 本章所有 code-cell 均用 .venv 中的 Python 执行
.venv/bin/python -c "import m2t, json, pathlib; print(m2t.__version__)"
```
