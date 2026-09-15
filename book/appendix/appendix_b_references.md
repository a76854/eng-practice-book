---
numbering: false
---

# 附录B 参考书目与延伸阅读

本附录按全书 12 章的知识点组织延伸阅读，分为“核心必读”（课程配套，1–2 本/章）与“进阶选读”（学有余力）。标注 `free` 的资源可直接在线获取。选书原则：与本书“以通用案例串联工程全链路”的定位互补，本书重可复现的最小闭环，参考书补单点的深度与“为什么”。

---

## 写作范式与全书气质

| 书名 | 定位 | 与本书的关系 |
|---|---|---|
| 《Dive into Deep Learning》（Aston Zhang 等，`free`） | 体例范式 | 本书直接沿用其 `code-cell` 自洽执行、渐进式讲解的写法，最贴近的体例参考 |
| 《构建之法》（邹欣） | 国内软件工程教材 | “工程+人+协作”三位一体的叙事，适合对照“如何把工程讲得不枯燥” |
| 《A Philosophy of Software Design》（John Ousterhout） | 工程思想 | 10 章讲透信息隐藏与复杂度控制，比《Clean Code》更适合学期课的复杂度讨论 |

---

## 第 1 至 2 章 软件工程筑基

Ch01 开发者的元技能

| 书名 | 类型 | 推荐理由 |
|---|---|---|
| 《Pro Git》（Scott Chacon，`free`） | 核心 | 分支与 PR 工作流的权威讲解，对照本章 1.3 节的 Git 协作实践 |
| 《Effective Python（第2版，Brett Slatkin）》 | 核心 | `pyproject.toml` / `venv` / `pathlib` / `subprocess` 的 Pythonic 实践 |
| 《The Pragmatic Programmer》（Hunt & Thomas） | 进阶 | “自动化一切”“不要重复自己”与本章脚本自动化的思想底座 |

Ch02 构筑代码质量的护城河

| 书名 | 类型 | 推荐理由 |
|---|---|---|
| 《Python Testing with pytest（Brian Okken）》 | 核心 | `fixture` / `mock` / 参数化的最佳实践，本章 2.3 节的直接对照 |
| 《代码大全（第2版，Steve McConnell）》 | 进阶 | 作为“过度设计”的反面教材，对照本章的类型与风格门禁取舍 |

---

## 第 3 至 6 章 后端开发全景与核心基石

Ch03 后端开发概览 / Ch04 HTTP 与 RESTful

| 书名 | 类型 | 推荐理由 |
|---|---|---|
| 《Designing Data-Intensive Applications》（Martin Kleppmann）第1–4章 | 核心 | 后端职责、契约与分层的“为什么”，覆盖第 3 至 6 章的全部权衡 |
| 《HTTP 权威指南》 | 核心 | 协议细节补充，对照 Ch04 的状态码与幂等性 |
| 《RESTful Web APIs》（Leonard Richardson） | 核心 | 成熟度模型与资源设计的进阶 |
| 《FastAPI 官方文档》（`free`） | 必读 | 本书后端选型的直接依据，OpenAPI 契约与依赖注入的权威来源 |

Ch05 数据持久化 / Ch06 并发模型与性能工程

| 书名 | 类型 | 推荐理由 |
|---|---|---|
| 《SQL 必知必会（第5版）》 | 核心 | “会写”层面，对应 Ch05 的 SQL 基础 |
| 《高性能 MySQL（第4版）》选读第3–4章 | 进阶 | 索引 / WAL / 锁的“为什么慢”，对照 Ch05 的 `EXPLAIN` / `WAL` |
| 《Fluent Python（第2版）》第19–21章 | 核心 | `GIL` / `asyncio` / `并发模型`的理论底座，对应 Ch06 |
| 《Designing Data-Intensive Applications》第5–12章 | 进阶 | 事务 / 复制 / 分区 / 一致性的体系化展开 |

---

## 第 8 至 9 章 前端协作与 Vue3 核心

Ch08 前端开发概况与工程化演进 / Ch09 Vue3 核心机制与状态设计

| 书名 | 类型 | 推荐理由 |
|---|---|---|
| 《Vue.js 设计与实现》（霍春阳） | 核心 | 响应式 / 组件化 / Pinia 的原理层，以后端视角理解前端 |
| 《JavaScript 高级程序设计（第4版）》选读 | 进阶 | 语言底座，查漏补缺 |
| 《前端工程化：体系设计与实践》 | 核心 | Vite / `package.json` / 模块化的前端镜像，对照 Ch01 的 `pyproject.toml` |

---

## 第 10 至 12 章 现代工程进阶与交付

Ch10 与外部世界的集成

| 书名 | 类型 | 推荐理由 |
|---|---|---|
| Redis 官方文档（`free`） | 核心 | 旁路缓存、过期策略与淘汰机制的权威来源，对照 Ch10 的缓存加速与三类缓存问题 |
| Apache Kafka 官方文档（`free`） | 核心 | 生产与消费、分区与幂等的权威来源，对照 Ch10 的重复投递与发件箱 |
| DeepSeek API 文档（`free`） | 必读 | 本书 LLM 调用示例的接口来源，流式响应与结构化输出可对照原文 |

Ch11 健壮性与安全底线 / Ch12 部署、容器化与持续集成

| 书名 | 类型 | 推荐理由 |
|---|---|---|
| 《Release It!（第2版，Michael Nygard）》 | 核心 | 错误边界 / 优雅降级 / 熔断的工程案例，对应 Ch11 |
| OWASP Top 10 官方文档（`free`） | 核心 | 校验 / 防注入 / JWT 的对照表 |
| 《Docker Deep Dive》（Nigel Poulton） | 核心 | `layer cache` / `depends_on`，对照 Ch12.1–12.3 |
| 《持续交付》（Jez Humble） | 进阶 | CI/CD 流水线的“为什么”，对应 Ch12.4 的 GitHub Actions 门禁 |
| Docker 官方 Best Practices（`free`） | 必读 | Dockerfile 多阶段构建与 COPY 顺序的权威来源 |

---

## 通用参考与工具文档

| 资源 | 说明 |
|---|---|
| MyST Markdown 官方文档（mystmd.org，`free`） | 本书构建链的权威来源，`{code-cell}` / `myst.yml` / `numbering` 的用法 |
| PEP 517 / 518 / 621（peps.python.org，`free`） | `pyproject.toml` 构建与元数据的规范原文 |
| GitHub Actions 官方文档（`free`） | Ch12 CI 流水线的 `workflow / job / step` 三层模型 |
| ruff / mypy / pytest 官方文档（`free`） | Ch02 代码质量工具的权威来源 |
