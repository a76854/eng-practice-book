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

> 小区门禁认"楼号+单元+房号"三样，差一样就不放行，哪怕你真是这栋楼的住户。同源策略也认三样：协议、域名、端口。开发时前端跑 `localhost:5173`、后端跑 `localhost:8000`，端口不同就是"跨域"，浏览器直接拦，连请求都不让发；curl、Postman 不是浏览器，门禁管不着。

契约对齐解决"两边说同一种话"，本节解决"话能不能送到"。开发期最经典的翻车是同一个接口换个工具结果不一样：后端用 Postman 调得通，前端在浏览器里一片红。本节在整章的位置是"过门禁"：先分清拦你的是谁，再选过关的方式。目的是让跨域报错从玄学变成一眼可辨的归属问题。

## 同源策略

为了防"甲页面读乙站点的数据"：你登录着银行，恶意页面若能借你的登录态读银行接口，后果不堪设想。所以协议、域名、端口三者必须完全相同才算同源，差任何一样，浏览器就认为是跨域请求：

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

## 预检

带自定义头（如 `Authorization`）或非简单方法的请求，浏览器会先发一个 OPTIONS 预检，真正的请求等预检通过才发。Network 面板里看到的两条记录，就是这一问一答：

```http
OPTIONS /api/favorites HTTP/1.1
Host: localhost:8000
Origin: http://localhost:5173
Access-Control-Request-Headers: authorization
```

```http
HTTP/1.1 204 No Content
Access-Control-Allow-Origin: http://localhost:5173
Access-Control-Allow-Headers: Authorization, Content-Type
```

看懂预检，联调时就多一眼：只有 OPTIONS、没有真正的 GET，说明预检没过，回后端查 CORS 配置；真正的请求回了 4xx，那是业务问题，不是跨域。

## 本节小结

- 拦你的是浏览器不是后端：协议、域名、端口差一样就算跨域，`localhost:5173` 调 `localhost:8000` 必跨。
- 后端用 CORS 响应头声明"我允许谁"，开发期放行 dev server，生产收紧到真实域名，不要配通配符。
- 复杂请求先发 OPTIONS 预检，Network 面板两条记录正常；只有预检没有正文是跨域问题，正文回 4xx 则是业务问题。
- 开发期可用 Vite 代理兜底（浏览器看是同源，转发是服务端行为），生产靠同域或正规 CORS。

金句：CORS 报错先别怪后端——先看是"浏览器拦的"还是"后端没回"，前者配跨域，后者查服务。
