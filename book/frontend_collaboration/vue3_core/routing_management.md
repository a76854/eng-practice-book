---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# 多页面与登录守卫

学完本节，你能回答：

- 单页应用里，页面切换为什么不需要整页刷新？路由在这里扮演什么角色？
- 路由表如何把 URL 映射到组件？`:id` 这种动态参数在前端怎么取？
- 未登录访问需要登录的页面时，前端在哪里拦截、怎么重定向？
- 为什么要按路由懒加载组件？它对首屏加载有什么影响？

组件解决了单个页面内部的拆分，但一个应用通常不止一个页面：列表、详情、登录。这一节讲前端如何在多个页面之间切换、如何守住“未登录不能进”这道门。

> 前端路由像一栋楼的前台加门禁。前台看门牌号（URL）把你带到对应的房间（组件），门禁在进房间前查你的身份（守卫），没权限就引你去登记（登录页）。而且房间只在你要进的那一瞬才点灯（懒加载），省下开灯的电。

这一节讲前端多页面的三件事：路由表定“哪个 URL 进哪个组件”，守卫定“能不能进”，懒加载定“首屏别一次全加载”。这三样正好对应后端的路由表、鉴权中间件与按需加载。

## 为什么需要路由

单页应用和多页应用的区别就在这：多页应用每次跳转都向服务器要一个新 HTML，整页刷新；单页应用把“页面切换”交给浏览器里的前端路由，只在浏览器内换视图，状态还能保留。所以路由的本质就是一张“URL 到组件”的映射表，和后端 `APIRouter` 里“路径到处理器”的映射是同一回事。

## 路由表

一个最小路由表，把三个页面挂到三个 URL 上：

```javascript
// router.ts
import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/tasks' },
    { path: '/tasks', component: () => import('./views/TaskList.vue') },
    { path: '/tasks/:id', component: () => import('./views/TaskDetail.vue') },
    { path: '/login', component: () => import('./views/Login.vue') },
  ],
})

export default router
```

`/tasks/:id` 里的 `:id` 是动态参数：访问 `/tasks/42` 就匹配到 `TaskDetail.vue`，组件里用 `route.params.id` 拿到 `42`。`redirect` 则把根路径 `/` 转到列表页。URL 默认走 history 模式（地址干净，如 `/tasks`）；另一种 hash 模式地址带 `#`（如 `/#/tasks`），无需服务端配合，用到时按需选择即可。

## 登录守卫

路由守卫做两件最常见的事：全局鉴权、参数校验。全局守卫 `beforeEach` 在每次跳转前执行，类似后端的 JWT 中间件；路由独享的 `beforeEnter` 只对某一条路由生效。

```javascript
// 全局守卫：未登录不给进需要鉴权的页面
router.beforeEach((to) => {
  const authed = !!localStorage.getItem('token')
  if (to.meta.requiresAuth && !authed) {
    return '/login'   // 重定向到登录页
  }
})

// 路由独享守卫：详情页先校验 id 是数字
{
  path: '/tasks/:id',
  beforeEnter: (to) => {
    if (!/^\d+$/.test(to.params.id)) return '/tasks'
  },
}
```

把 `requiresAuth: true` 标在需要登录的路由上，守卫就能按标记拦截。记住一点：**前端守卫管的是体验，真正的安全永远以后端鉴权为准**，前端拦截只是“提前拦住、少走一趟”。

## 懒加载

路由表里 `component: () => import('./views/TaskList.vue')` 是动态导入。Vite 会把每个这样的组件拆成独立的 chunk，访问到那条路由时才下载，首屏只加载首页必需的代码。

```javascript
// 动态导入：访问时才加载该页面的代码
const TaskDetail = () => import('./views/TaskDetail.vue')
```

一句话理解：不懒加载，首屏要把所有页面代码一次性下完；懒加载之后，首屏只下当前页，切到别的页再按需下。对页面多的后台应用，这是首屏明显变快的来源。

## 本节小结

- 路由是“URL 到组件”的映射表，`:id` 动态参数对应一组路径，`redirect` 管默认跳转。
- 全局守卫 `beforeEach` 做鉴权拦截，路由独享 `beforeEnter` 做参数校验，分别对应后端的鉴权中间件与参数校验。
- 懒加载用动态 `import()` 按路由拆包，访问时才下载，首屏只加载当前页。
- 前端守卫管体验、后端鉴权管安全，两者职责不混。

金句：路由把“看哪个页面”从“刷新整个网站”里拆了出来，守卫在门口把关，懒加载在幕后省流量，三件事合起来就是前端的多页面。