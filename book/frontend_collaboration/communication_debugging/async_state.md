---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# 异步状态

学完本节，你能回答：

- 为什么一次搜索在界面上对应四种状态，而不是"有数据 / 没数据"两种？
- `loading` / `error` / `data` 三元组和散落的布尔值相比，好在哪？
- "先搜 pydantic、紧接着搜 fastapi，结果却显示 pydantic"是怎么发生的？怎么规避？

> 等外卖时，App 显示"商家已接单、骑手取餐中、预计送达"，而不是只有"没到 / 到了"。异步请求的界面也一样：在途、成功、失败、还没开始，是四种不同的样子，少画一种，用户就多一次困惑。

请求是异步的：点下搜索到结果回来，中间隔着一次网络往返，这段时间界面不能卡死，也不能装作已经有结果。上一节解决"怎么发"，本节解决"发出之后、结果回来之前，界面该是什么样"。本节在整章的位置是"等"：目的是给等待一个确定的形状，让每种局面都有对应的界面；再给迟到的旧响应立一条规矩，不让它盖错正在显示的新结果。

## 四种状态，一个都不能少

搜索框点下搜索之后，界面有四种可能：

| 状态 | 界面 | 对应的数据 |
| --- | --- | --- |
| 还没搜 | 搜索框 + 一句提示 | `query = ''`，`results = []` |
| 正在搜 | 转圈 / 骨架屏 | `loading = true` |
| 搜到了 | 结果列表 | `results = [...]` |
| 搜失败了 | 错误提示 + 重试按钮 | `error = '...'` |

漏掉任何一种都是坑：没有"正在搜"，用户会反复点按钮发重复请求；没有"搜失败了"，断网时页面一片空白，用户不知道发生了什么；没有"搜到了但为空"（空数组），用户分不清是"还没搜"还是"搜了但没结果"。

朴素的写法用几个散落的布尔值各自为政：`loading`、`error`、`results` 三个变量分别 `ref`，模板里用一串 `v-if` 拼。写对也能跑，但有一个隐性风险：三个值之间没有"互斥"约束，理论上会出现 `loading = true` 的同时 `error` 也有值这种不可能组合。

结构化的写法是 `loading` / `error` / `data` 三元组当作一个整体来维护：第 9 章 Pinia 那节的 `useSearch` store 就是这个形状——`search()` 一开始就把 `loading` 置 true、`error` 清空，成功写 `results`、失败写 `error`，`finally` 里关掉 `loading`。三者同生共灭，模板的三个 `v-if` 永远只亮一个。

```vue
<!-- 搜索结果区：三态互斥，只亮一个 -->
<p v-if="loading">加载中...</p>
<p v-else-if="error">搜索失败：{{ error }} <button @click="search">重试</button></p>
<ul v-else>
  <li v-for="r in results" :key="r.url">{{ r.title }}</li>
</ul>
```

## 竞态

三元组管住了"同时只能亮一个"，但还有一类更隐蔽的错：**竞态**。用户先搜"pydantic"，没等结果回来又搜"fastapi"，两个请求在路上赛跑。如果先发的"pydantic"后到，它会把"正在显示 fastapi 结果"的界面又覆盖成 pydantic 的——用户明明搜的是 fastapi，看到的却是 pydantic 的结果。

根因是"后发的请求没有让先发的失效"。规避的办法有两个，按场景选：

1. **序号牌**：每次搜索发一个递增序号回来时对一下，序号对不上就丢弃。简单，纯前端就能做，适合搜索框这种高频触发。
2. **取消旧请求**：新搜索发出前，用 `AbortController` 把上一个没回来的请求取消掉。更彻底，但要处理"取消"本身也是一种需要被忽略的错误。

```javascript
// 序号牌：只认最新一次搜索的结果
let latestSeq = 0

async function search(keyword) {
  const seq = ++latestSeq
  loading.value = true
  try {
    const data = await fetch(`/api/search?q=${keyword}`).then(r => r.json())
    if (seq !== latestSeq) return   // 不是最新的，丢弃
    results.value = data
  } finally {
    if (seq === latestSeq) loading.value = false
  }
}
```

第 9 章 `watch(query, ...)` 自动搜索的写法，更是竞态的重灾区——每敲一个字母都发一次请求。真实产品要么加防抖（停 300 毫秒没再输入才发），要么用序号牌，二者至少要有一个。

## 防抖

序号牌管"迟到"，防抖管"发太多"。输入框每敲一个字母就发一次请求，既浪费，又把竞态概率拉满。防抖的思路是等用户停手再发：

```javascript
// 防抖：停 300 毫秒没再输入，才真正发请求
function debounce(fn, wait = 300) {
  let timer = null
  return (...args) => {
    clearTimeout(timer)
    timer = setTimeout(() => fn(...args), wait)
  }
}

const onInput = debounce((keyword) => search(keyword), 300)
```

防抖与序号牌不互斥：防抖减少请求次数，序号牌兜住剩下的乱序。自动搜索的输入框两个至少要有一个，文档搜索用防抖起步就够。

## 本节小结

- 异步请求对应四种界面状态（没搜、正在搜、搜到了、搜失败了），"为空结果"和"还没搜"要分开。
- `loading` / `error` / `data` 三元组同生共灭，比散落布尔值更不容易出现不可能组合。
- 竞态是"后发的请求先到、先发的后到把界面盖错"，用序号牌丢弃过期响应，或取消旧请求。
- 输入框自动搜索必须配防抖（停手 300 毫秒再发）或序号牌，否则每敲一字母一次请求，竞态必现。

金句：异步界面的错，一半是"状态没画全"，另一半是"旧请求没认输——给每次请求发一块序号牌，只认最新的。
