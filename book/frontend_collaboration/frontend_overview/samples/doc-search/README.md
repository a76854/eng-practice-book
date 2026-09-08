# 文档搜索示例（samples/doc-search）

这是第 8 章"前端开发概况与工程化演进"配套的最小前端样例，用于演示"前后端分离下，前端如何把 `GET /api/search?q=...` 返回的 JSON 渲染成页面"。

- `index.html`：一个真实的静态页面，内联了与正文契约一致的 mock 搜索结果，渲染一个结果列表。
- `screenshot.mjs`：用 Playwright 打开 `index.html` 并截图，产出一张确定性的页面截图。

## 本地打开

直接用浏览器打开 `index.html` 即可，无需任何构建或依赖安装。

## 重新截图

```bash
npm install          # 安装 playwright
npm run screenshot   # 生成 ../../figs/frontend_overview_search.png
```

截图输出目录 `figs/` 是正文引用图片的唯一来源，请保持文件名稳定，正文引用才不会断。
