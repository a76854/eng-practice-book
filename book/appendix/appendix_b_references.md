# 附录B 参考书目与延伸阅读

本附录按全书五篇结构与 11 章知识点组织延伸阅读，分为“核心必读”（课程配套，1–2 本/章）与“进阶选读”（学有余力）。标注 `免费` 的资源可直接在线获取。选书原则：与本书“以通用案例串联工程全链路”的定位互补——本书重可复现的最小闭环，参考书补单点的深度与“为什么”。

> 使用建议：每章只读 1 本核心书的对应章节即可；不要贪多。教师可在每章末“思考题”后指定 1 本作为课后精读。

---

## 写作范式与全书气质

| 书名 | 定位 | 与本书的关系 |
|---|---|---|
| 《Dive into Deep Learning》（Aston Zhang 等，免费） | 体例范式 | 本书直接沿用其 `code-cell` 自洽执行、渐进式讲解的写法，最贴近的体例参考 |
| 《构建之法》（邹欣） | 国内软件工程教材 | “工程+人+协作”三位一体的叙事，适合对照“如何把工程讲得不枯燥” |
| 《A Philosophy of Software Design》（John Ousterhout） | 工程思想 | 10 章讲透信息隐藏与复杂度控制，比《Clean Code》更适合学期课的复杂度讨论 |

---

## 第一篇 软件工程筑基（Ch01 开发者的元技能 / Ch02 代码质量护城河）

### Ch01 开发者的元技能

| 书名 | 类型 | 推荐理由 |
|---|---|---|
| 《Pro Git》（Scott Chacon，免费） | 核心 | 分支与 PR 工作流的权威讲解，对照本章 1.5 节的 Git 协作实践 |
| 《Effective Python（第2版，Brett Slatkin）》 | 核心 | `pyproject.toml` / `venv` / `pathlib` / `subprocess` 的 Pythonic 实践 |
| 《The Pragmatic Programmer》（Hunt & Thomas） | 进阶 | “自动化一切”“不要重复自己”与本章脚本自动化的思想底座 |

### Ch02 构筑代码质量的护城河

| 书名 | 类型 | 推荐理由 |
|---|---|---|
| 《Python Testing with pytest（Brian Okken）》 | 核心 | `fixture` / `mock` / 参数化的最佳实践，本章 2.4 节的直接对照 |
| 《代码大全（第2版，Steve McConnell）》 | 进阶 | 作为“过度设计”的反面教材，对照本章的类型与风格门禁取舍 |

---

## 第二篇 后端开发全景与核心基石（Ch03–Ch06）

### Ch03 后端开发到底是什么 / Ch04 HTTP 与 RESTful

| 书名 | 类型 | 推荐理由 |
|---|---|---|
| 《Designing Data-Intensive Applications》（Martin Kleppmann）第1–4章 | 核心 | 后端职责、契约与分层的“为什么”，覆盖 Part2 的全部权衡 |
| 《HTTP 权威指南》 | 核心 | 协议细节补充，对照 Ch04 的状态码与幂等性 |
| 《RESTful Web APIs》（Leonard Richardson） | 核心 | 成熟度模型与资源设计的进阶 |
| 《FastAPI 官方文档》（免费） | 必读 | 本书后端选型的直接依据，OpenAPI 契约与依赖注入的权威来源 |

### Ch05 数据持久化 / Ch06 并发模型与性能工程

| 书名 | 类型 | 推荐理由 |
|---|---|---|
| 《SQL 必知必会（第5版）》 | 核心 | “会写”层面，对应 Ch05 的 SQL 基础 |
| 《高性能 MySQL（第4版）》选读第3–4章 | 进阶 | 索引 / WAL / 锁的“为什么慢”，对照 Ch05 的 `EXPLAIN` / `WAL` |
| 《Fluent Python（第2版）》第19–21章 | 核心 | `GIL` / `asyncio` / `并发模型`的理论底座，对应 Ch06 |
| 《Designing Data-Intensive Applications》第5–12章 | 进阶 | 事务 / 复制 / 分区 / 一致性的体系化展开 |

---

## 第三篇 前端协作与现代前端基础（Ch07–Ch08）

| 书名 | 类型 | 推荐理由 |
|---|---|---|
| 《Vue.js 设计与实现》（霍春阳） | 核心 | 响应式 / 组件化 / Pinia 的原理层，以后端视角理解前端 |
| 《JavaScript 高级程序设计（第4版）》选读 | 进阶 | 语言底座，查漏补缺 |
| 《前端工程化：体系设计与实践》 | 核心 | Vite / `package.json` / 模块化的前端镜像，对照 Ch01 的 `pyproject.toml` |

---

## 第四篇 现代工程进阶与交付（Ch09–Ch11）

### Ch09 与外部世界的集成（ASR 与 LLM）

| 书名 | 类型 | 推荐理由 |
|---|---|---|
| FunASR / ModelScope 官方文档（免费） | 必读 | ASR 接入的直接依据，对照 Ch09 的重采样与归一化 |
| OpenAI / 通义千问 API 文档（免费） | 必读 | LLM 接口设计与流式响应的权威来源 |

### Ch10 健壮性与安全底线 / Ch11 部署、容器化与持续集成

| 书名 | 类型 | 推荐理由 |
|---|---|---|
| 《Release It!（第2版，Michael Nygard）》 | 核心 | 错误边界 / 优雅降级 / 熔断的工程案例，对应 Ch10 |
| OWASP Top 10 官方文档（免费） | 核心 | 校验 / 防注入 / JWT 的对照表 |
| 《Docker Deep Dive》（Nigel Poulton） | 核心 | `layer cache` / `depends_on`，对照 Ch11.1–11.3 |
| 《持续交付》（Jez Humble） | 进阶 | CI/CD 流水线的“为什么”，对应 Ch11.4 的 GitHub Actions 门禁 |
| Docker 官方 Best Practices（免费） | 必读 | Dockerfile 多阶段构建与 COPY 顺序的权威来源 |

---

## 通用参考与工具文档

| 资源 | 说明 |
|---|---|
| MyST Markdown 官方文档（mystmd.org，免费） | 本书构建链的权威来源，`{code-cell}` / `myst.yml` / `numbering` 的用法 |
| PEP 517 / 518 / 621（peps.python.org，免费） | `pyproject.toml` 构建与元数据的规范原文 |
| GitHub Actions 官方文档（免费） | Ch11 CI 流水线的 `workflow / job / step` 三层模型 |
| ruff / mypy / pytest 官方文档（免费） | Ch02 代码质量工具的权威来源 |

---

## 选用策略（给教师）

1. **每章只配 1 本核心**：已在上表标注“核心”，其余为选读，避免学生负担过重。
2. **优先推免费资源**：Pro Git、d2l、FastAPI 文档、OWASP Top 10、MyST 文档均可在线直接阅读。
3. **本书的差异化**：上述书均为单点深入，而本书用通用案例把 Part1→Part4 串成可复现的闭环——这是现有教材中稀缺的定位，可在前言中明确强调。
