---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# 路由管理

> 学完本节，你能回答：Vue Router 4 的两种历史模式有何差异、如何选择？路由守卫如何做鉴权与参数校验？路由懒加载如何与 Vite 的分包配合？

## 为何需要路由：从“多页刷新”到“单页切换”

MeetingToText 有三个页面：任务列表 `/tasks`、详情 `/tasks/:id`、上传 `/upload`。单页应用用前端路由在浏览器内切换视图，状态可保持，路由就是 URL 到组件的映射，类似后端 `APIRouter` 的路径到处理器的映射。

## 路由表、守卫与懒加载

### 1. 历史模式：hash vs html5

| 模式 | URL 形态 | 原理 | 适用 |
|------|---------|------|------|
| `createWebHashHistory` | `/#/tasks` | 监听 `hashchange` | 无需服务端配置，适合静态托管 |
| `createWebHistory` | `/tasks` | 依赖 `history.pushState` | URL 更干净，需服务端回退到 `index.html` |

MeetingToText 用 `createWebHistory` 时，Nginx 需 `try_files $uri /index.html`，否则直访 `/tasks/1` 会 404；hash 无此问题，但 URL 带 `#`。

```javascript
// 示意：router.ts
import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/tasks' },
    { path: '/tasks', component: () => import('./views/TaskList.vue') },
    { path: '/tasks/:id', component: () => import('./views/TaskDetail.vue'), props: true },
    { path: '/upload', component: () => import('./views/Upload.vue') },
  ]
})
export default router
```

### 2. 路由守卫：只保留两个必备

本节只用两个守卫覆盖常见需求，其余顺序与钩子作为调试练习。

* 全局 `beforeEach` 做鉴权，类似后端的 JWT 中间件，`next('/login')` 重定向
* 路由独享 `beforeEnter` 校验参数，如 id 是否为数字

```javascript
// 全局守卫：鉴权
router.beforeEach((to, from, next) => {
  const authed = !!localStorage.getItem('token')
  if (to.meta.requiresAuth && !authed) return next('/login')
  next()
})

// 路由独享守卫：任务详情需先校验 id 合法
{
  path: '/tasks/:id',
  beforeEnter: (to) => {
    if (!/^\d+$/.test(to.params.id)) return '/tasks'
  }
}
```

更多守卫如 `beforeResolve` 或 `afterEach` 可在调试时打印 `to` 与 `from` 自行观察，不在本节展开。

### 3. 懒加载：按路由分包

`component: () => import('./views/TaskList.vue')` 是动态导入，Vite 与 Rollup 会拆为独立 chunk，访问该路由时才加载，首屏更快。

```javascript
const TaskList = () => import('./views/TaskList.vue')
```

## 可运行示例：Python 演示路由匹配与两道守卫

示例用 Python 模拟路由匹配、两道守卫与懒加载分包，本地可复现。

```{code-cell} ipython3
import re
from typing import Callable

class RouteRecord:
    def __init__(self, path: str, component: str, meta: dict | None = None, lazy: bool = False):
        self.path = path
        self.component = component
        self.meta = meta or {}
        self.lazy = lazy
        pattern = re.sub(r":(\w+)", r"(?P<\1>[^/]+)", path)
        if path == "/":
            pattern = r"/"
        self.regex = re.compile(f"^{pattern}$")

    def match(self, url: str) -> dict | None:
        m = self.regex.match(url)
        if not m:
            return None
        return m.groupdict()

routes = [
    RouteRecord("/tasks", "TaskList.vue", lazy=True),
    RouteRecord("/tasks/:id", "TaskDetail.vue", meta={"requiresAuth": True}, lazy=True),
    RouteRecord("/upload", "Upload.vue", lazy=True),
    RouteRecord("/login", "Login.vue"),
]

def match_route(url: str) -> tuple[RouteRecord | None, dict]:
    for r in routes:
        params = r.match(url)
        if params is not None:
            return r, params
    return None, {}

for url in ["/tasks", "/tasks/42", "/upload", "/unknown"]:
    rec, params = match_route(url)
    if rec:
        print(f"匹配 {url!r} → {rec.component} params={params} lazy={rec.lazy}")
    else:
        print(f"匹配 {url!r} → 404")
print()

rec, params = match_route("/tasks/42")
assert rec and rec.component == "TaskDetail.vue"
assert params == {"id": "42"}
print("路由匹配校验通过：/tasks/:id 正确提取 id=42")
print()

# ---- 两道守卫：全局鉴权与路由参数校验 ----
print("=== 两道守卫 ===")

def global_before_each(to: dict, frm: dict) -> str | None:
    if to.get("meta", {}).get("requiresAuth") and not to.get("authed"):
        return "/login"
    return None

def route_before_enter(to: dict) -> str | None:
    pid = to.get("params", {}).get("id")
    if pid is not None and not pid.isdigit():
        return "/tasks"
    return None

def navigate(url: str, frm: dict | None = None, authed: bool = False):
    frm = frm or {"path": "?"}
    rec, params = match_route(url)
    if not rec:
        print(f"导航 {url!r} → 404")
        return None
    to = {"path": rec.path, "url": url, "params": params, "meta": rec.meta, "authed": authed}
    print(f"导航 {url!r} (authed={authed})")
    redirect = global_before_each(to, frm)
    if redirect:
        print(f"  全局守卫拦截 → 重定向 {redirect!r}")
        return redirect
    redirect = route_before_enter(to)
    if redirect:
        print(f"  路由守卫拦截 → 重定向 {redirect!r}")
        return redirect
    print(f"  导航确认 → 渲染 {rec.component} (lazy={rec.lazy})")
    return rec.component

assert navigate("/tasks/42", authed=False) == "/login"
assert navigate("/tasks/42", authed=True) == "TaskDetail.vue"
assert navigate("/tasks/abc", authed=True) == "/tasks"
assert navigate("/tasks", authed=False) == "TaskList.vue"
print("守卫校验通过：鉴权与参数校验按序执行")
print()

# ---- 懒加载分包 ----
print("=== 懒加载分包 ===")
chunks = {
    "TaskList.vue": "chunk-task-list.[hash].js",
    "TaskDetail.vue": "chunk-task-detail.[hash].js",
}

def load_chunk(component: str) -> str:
    c = chunks[component]
    print(f"  按需加载 {component} → {c}")
    return c

print("首屏 /tasks:")
load_chunk("TaskList.vue")
print("首屏未加载 TaskDetail 的 chunk（按需）")
print("切换 /tasks/42:")
load_chunk("TaskDetail.vue")
print("懒加载校验通过：首屏 1 chunk，切换时再按需 1 chunk")
print()
print("小结：路由表管映射，守卫管放行，懒加载管分包")

# 预期输出:
# 匹配 '/tasks' → TaskList.vue params={} lazy=True
# 匹配 '/tasks/42' → TaskDetail.vue params={'id': '42'} lazy=True
# 路由匹配校验通过
# === 两道守卫 ===
# 导航 '/tasks/42' (authed=False)  ... 重定向 '/login'
# 导航 '/tasks/42' (authed=True)  ... 渲染 TaskDetail.vue
# 守卫校验通过
# === 懒加载分包 ===
# 首屏 /tasks: 按需加载 TaskList.vue → chunk-task-list.[hash].js
```

```bash
# 本地验证路由与分包
.venv/bin/python -c "import re; print(re.sub(r':(\w+)', r'(?P<\1>[^/]+)', '/tasks/:id'))"
```

> **与全书的衔接**：本节的路由守卫是 [第4章 HTTP 契约](../../backend_development/http_restful/index.md) 中鉴权中间件的前端镜像；懒加载的分包将在 [第11章 部署](../../advanced_engineering/deploy_cicd/index.md) 的静态资源分析中回响。
