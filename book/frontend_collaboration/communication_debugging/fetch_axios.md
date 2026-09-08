---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# 发出请求：fetch 与 axios

学完本节，你能回答：

- 浏览器原生 `fetch` 发一次请求要写哪几步？它默认"帮"你做了什么、"没帮"你做什么？
- `axios` 相对 `fetch` 多了哪些能力？拦截器解决什么问题？
- 什么时候直接用 `fetch` 就够，什么时候该上 `axios`？

上一节画清了整条链路，这一节看链路的第一步：前端怎么把请求发出去。发请求的工具就两个主流选择，原生的 `fetch` 和库 `axios`。

> 自己寄快递，要自己打包、自己填单、自己送到驿站；叫快递员上门，他带箱子、带面单、带保价，还能全程追踪。`fetch` 像自己寄，轻但什么都要自己来；`axios` 像叫上门，顺手但多一个依赖。寄什么不重要，怎么寄、丢了怎么办，才是选型的依据。

## fetch：浏览器自带的

`fetch` 是浏览器原生的请求 API，返回一个 Promise。发一次搜索请求长这样：

```javascript
// fetch：发请求、判状态、转 JSON，三步都要手写
const res = await fetch('/api/search?q=pydantic')
if (!res.ok) throw new Error(`HTTP ${res.status}`)
const results = await res.json()   // 响应体默认是流，要手动转成 JSON
```

`fetch` 的三件事要记牢：

1. **只管发，不管对错**：网络不通它会抛错，但后端回 404、500 它不抛，`res.ok` 要自己判断。
2. **响应体默认是流**：`res.json()`、`res.text()` 要手动调一次。
3. **超时、重试、默认头**统统没有，要自己包一层。

正因为"什么都不包"，`fetch` 最轻、零依赖，简单场景一行就能用。

## axios：包了一层顺手的

`axios` 在 `fetch` 之上包了工程里反复要写的那些事：

```javascript
// axios：自动转 JSON、非 2xx 自动抛错
import axios from 'axios'

const api = axios.create({
  baseURL: '/api',        // 前缀统一收敛，后面只写路径
  timeout: 8000,          // 超时统一 8 秒
})

const { data } = await api.get('/search', { params: { q: 'pydantic' } })
// data 已经是解析好的 JSON；404/500 会自动抛错进 catch
```

| 维度 | fetch | axios |
| --- | --- | --- |
| 需不需要装 | 浏览器自带 | 要装包 |
| 响应体 | 手动 `.json()` | 自动解析 |
| 错误 | 4xx/5xx 不抛，要判 `res.ok` | 非 2xx 自动抛 |
| 超时/重试 | 没有，要自己写 | `timeout` 自带，重试配拦截器 |
| 拦截器 | 没有 | 请求/响应拦截器（统一加 token、统一打日志） |

拦截器是 `axios` 最值钱的一件：登录后拿到的 token，每个请求都要在 header 里带上；出错时想统一弹提示。没有拦截器，每个 `fetch` 调用处都要重复这两件事。有了它：

```javascript
// 请求拦截器：每次请求自动带上登录态
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})
```

## 怎么选

一句话：**页面少、请求少、没登录态，用 `fetch`；稍成规模、有鉴权、有统一错误处理，上 `axios`**。对文档搜索这种带登录（收藏页要鉴权）的应用，`axios` 更省事，`baseURL` + 拦截器 + 超时三件一次配好，后面只管调。

选型和"谁强谁弱"无关，只和"你要不要自己写那些重复"有关。第 9 章的 `useSearch` 组合函数里，把上面这段 `api.get` 装进去，就是前端的请求层。

## 本节小结

- `fetch` 轻而裸：发请求、判状态、转 JSON 三步都要手写，适合简单场景。
- `axios` 包了工程常用件：自动 JSON、非 2xx 抛错、超时、拦截器，适合稍成规模的应用。
- 拦截器解决"每个请求都要带的公共逻辑"（token、日志、错误提示），避免散落各处。
- 选型看规模与公共逻辑，不看流行度：文档搜索带登录态，用 `axios` 更合适。

金句：发请求的难处从来不在"发"，而在"每次都要带的那些东西"，谁替你收敛了它们，你就选谁。
