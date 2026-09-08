---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# CORS 与开发代理

学完本节，你能回答：

- 同样的接口，为什么 curl 能调通、浏览器里一调就报 CORS 错？
- 同源策略的"同源"指哪三样相同？`http://localhost:5173` 调 `http://localhost:8000` 为什么算跨域？
- 后端配 CORS 要开哪几个头？开发期不想动后端代码时怎么兜底？

开发期最经典的翻车现场：后端说"我这边 Postman 调 200 了"，前端说"我这边一片红，CORS 报错"。同一个接口，换个工具结果就不一样。这一节讲这道"浏览器替安全拦的关"是什么、怎么过。

> 小区门禁认"楼号+单元+房号"三样，差一样就不放行，哪怕你真是这栋楼的住户。同源策略也认三样：协议、域名、端口。开发时前端跑 `localhost:5173`、后端跑 `localhost:8000`，端口不同就是"跨域"，浏览器直接拦，连请求都不让发——至于 curl、Postman，它们不是浏览器，门禁管不着。

## 同源策略认哪三样

同源指协议、域名、端口三者完全相同。差任何一样，浏览器就认为是跨域请求：

| 前端页面 | 后端接口 | 结论 |
| --- | --- | --- |
| `http://localhost:5173` | `http://localhost:8000/api/search` | 跨域（端口不同） |
| `http://localhost:5173` | `http://localhost:5173/api/search` | 同源 |
| `https://app.example.com` | `http://api.example.com/search` | 跨域（协议+域名都不同） |

注意拦你的是**浏览器**，不是后端。后端其实收到了请求、也回了 200，但浏览器看到响应里没有"我允许这个来源"的声明，就把响应扣下不给页面。这就是"curl 能通、浏览器不行"的全部原因。

## CORS 响应头

后端放行的方式，是在响应里声明"我允许谁来调我"：

```python
# 后端：FastAPI 配 CORS 中间件（开发期放行前端开发服务器）
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],   # 只放行前端开发服务器
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
```

生产环境把 `allow_origins` 收紧到真实前端域名，不要图省事配 `["*"]`——带鉴权的接口配通配符，等于把门禁拆了。复杂请求（带自定义头、非简单方法）浏览器会先发一个 OPTIONS 预检，真正的请求等预检通过才发，这是联调时 Network 面板里看到两条记录的原因。

## 开发期代理

如果暂时不想动后端代码（比如后端是别人的服务），开发期可以用 Vite 代理兜底：让浏览器以为请求还是发给同源的 `/api`，Vite 在背后转发给真正的后端：

```javascript
// vite.config.ts
export default {
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
}
```

浏览器看到的是"同源请求"（都发给 5173），门禁不拦；Vite 转发时是服务端对服务端，没有浏览器的同源限制。注意这只是开发期的拐杖，生产环境前端与后端同域部署或配好 CORS 才是正解。

## 本节小结

- 拦你的是浏览器不是后端：协议、域名、端口差一样就算跨域，`localhost:5173` 调 `localhost:8000` 必跨。
- 后端用 CORS 响应头声明"我允许谁"，开发期放行 dev server，生产收紧到真实域名，不要配通配符。
- 复杂请求会先发 OPTIONS 预检，Network 面板看到两条记录是正常的。
- 开发期可用 Vite 代理兜底（浏览器看是同源，转发是服务端行为），生产靠同域或正规 CORS。

金句：CORS 报错先别怪后端——先看是"浏览器拦的"还是"后端没回"，前者配跨域，后者查服务。
