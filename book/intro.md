---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
    format_version: '0.13'
    jupytext_version: 1.16.4
kernelspec:
  display_name: Python 3
  language: python
  name: python3
numbering:
  title:
    enabled: false
---

# 《算法编程与工程实践》简介

《算法编程与工程实践》是一本面向中文读者的可运行教材，以「增量重建 MeetingToText」为贯穿主线，采用 Jupyter Book 与 MyST Markdown 构建。全书 16 章螺旋课纲（13 个教学单元 + 3 个里程碑），每个单元聚焦一个工程主题，配合可执行代码与「改动并预测」实验，帮助读者在实践中掌握算法编程与工程协作的核心能力。

本页用于验证 Jupyter Book 的执行链路。下方的代码单元通过 `myst-nb` 的 `{code-cell}` 指令执行，构建时由 `execute.execute_notebooks: cache` 驱动，确保全书「可运行」的核心机制已就绪。


```{code-cell} ipython3
print("Hello, eng-practice-book!")
```
