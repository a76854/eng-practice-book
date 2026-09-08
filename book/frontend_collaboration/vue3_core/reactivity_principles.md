---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# 数据如何驱动视图

学完本节，你能回答：

- 用浏览器原生方式让"数据一变、界面就变"，为什么又累又容易错？
- `ref` 和 `reactive` 解决了什么问题？为什么 `ref` 在 JavaScript 里要写 `.value`？
- `computed` 和 `watch` 的分工是什么？什么情况下用哪个？
- 看到一个页面，你能说出它的数据、派生值和副作用分别是什么吗？

上一节把数据写进了页面：模板里写 `{{ result.title }}`、`v-for="r in results"`，数据一到页面就摆好了。可还差一件最关键的事没讲：你改了 `results`，下面的结果列表为什么会自己跟着变？这一节掀开这层幕布，看响应式。

> 你在表格里写下公式 `=A1+A2`，改 A1，结果格自己就重算了，不用手动刷新。响应式就是想让界面变成这样一张表：你只负责改数据，派生和刷新都自动发生。下面要讲的三件事，存数据、算派生、做副作用，都是在为这张表添零件。

这一节只讲三个最常用的接口：`ref`、`computed`、`watch`。顺序不是随意排的：先有数据（`ref`），才能有派生（`computed`），派生值变化时才谈得上副作用（`watch`）。顺着这条线走一遍，比背三个定义有用得多。

## 没有响应式之前，这活有多累

回到第 8 章那个文档搜索样例。它用最朴素的方式，把一个搜索结果 JSON 画成列表：

```javascript
// 原生写法：fetch 之后，每一条结果都要手动建节点
const list = document.getElementById('results')

async function load(keyword) {
  const res = await fetch(`/api/search?q=${keyword}`)
  const results = await res.json()
  list.innerHTML = ''
  for (const r of results) {
    const li = document.createElement('li')
    const a = document.createElement('a')
    a.href = r.url
    a.textContent = r.title
    li.appendChild(a)
    list.appendChild(li)
  }
}

load('pydantic')
```

这几条结果还算少。往后推一步：关键词一换就要重新请求、清空再重建一次列表；加一个"加载中"的遮罩，又是一处要手动显隐；再加错误提示，再一处。真正有用的信息其实只有一条：`results` 和 `query` 会变。可为了让界面跟得上，你得自己数着"有哪几次变化要同步"，漏掉任何一次，界面就与数据对不上。数据在 A 处，界面在 B 处，中间那根同步的线要你亲手牵着。响应式的全部含义，就是把牵线这件事交给框架。

## ref：让一个值变成可观测的

为什么普通变量不行？因为 `let query = 'pydantic'` 这种赋值，JavaScript 本身提供不了"被修改了就通知一声"的能力，你改了它谁都收不到消息。Vue 用 `ref` 把值装进一层盒子，你通过 `query.value` 读写，读写都经过这个盒子，Vue 才有机会知道你改了什么。

```javascript
import { ref } from 'vue'

const query = ref('')         // 搜索关键词
const results = ref([])       // 搜索结果，先空着
const loading = ref(false)    // 是否在加载中

query.value = 'pydantic'      // JavaScript 里读写都要 .value
console.log(query.value)      // pydantic
```

这也就顺带回答了初学者最常问的问题：为什么模板里不用 `.value`、JavaScript 里却要？因为模板是 Vue 自己解析的，它认得 `ref` 这个盒子，会自动帮你拆开；而 JavaScript 代码是你写的，Vue 没法替你拆，你就得自己 `.value`。`.value` 不是多此一举，它是"读写要经过盒子"这件事在代码里留下的痕迹。

`ref` 装的是单值。要装对象和数组，有它的兄弟 `reactive`，它让对象的每一层都可观测：

```javascript
import { reactive } from 'vue'

const form = reactive({ query: 'pydantic', limit: 10 })
form.query = 'fastapi'   // 直接改属性，视图跟得上
```

两者怎么选，一张表就够：

| | ref | reactive |
| --- | --- | --- |
| 装什么 | 单值：字符串、数字、布尔 | 对象、数组 |
| 怎么读写 | JavaScript 里 `.value`，模板里不用 | 直接 `.属性` |
| 什么时候用 | 单个输入、开关、计数 | 一组彼此相关的状态（如表单） |

## computed：把算出来的值声明出来

现在有了 `results`，页面还想要一条"搜索结果共 N 条"的提示。你当然可以每次用到时现算：

```javascript
const count = results.value.length
```

这么写能跑，但有两个毛病：一是每次界面更新都重新数一遍，哪怕 `results` 根本没变；二是"计数"这段逻辑散落在模板和代码各处，改起来要到处翻。`computed` 就是冲这两点来的：它把"由谁算出"声明一次，框架替你缓存，依赖没变就不重算。

```javascript
import { ref, computed } from 'vue'

const results = ref([])
// 声明一个派生值：由 results 推出，依赖不变就复用上次结果
const resultCount = computed(() => results.value.length)
```

`computed` 对应的后端心智是"物化视图"：底层数据变了，这个视图自动刷新；没人动底层数据时，它把上次算好的结果直接还给你。后端查库也有一样的设计，常用查询建个物化视图，省得每次重算。

## watch：给变化挂一个反应

`computed` 管的是"算出一个值"，但有些事不是算值能解决的：关键词一换，你要重新发个请求。这种"值变了就要去做"的动作，归 `watch` 管。

```javascript
import { ref, watch } from 'vue'

const query = ref('')
const results = ref([])
const loading = ref(false)

// query 一变，就执行这段副作用：按新关键词重新搜索
watch(query, async (nv) => {
  loading.value = true
  results.value = await fetch(`/api/search?q=${nv}`).then(r => r.json())
  loading.value = false
})
```

真实产品里，输入框触发搜索通常会加一个防抖，避免每敲一个字母都发一次请求；那句防抖就是"副作用该怎么触发"的工程细节。至此，几个接口的分工可以一句话钉死：

| | 管什么 | 一句话 |
| --- | --- | --- |
| ref / reactive | 存数据 | 可观测的容器 |
| computed | 算派生 | 由别的值推出、带缓存 |
| watch | 做副作用 | 值变了顺手做点事 |

用后端的话再翻译一遍：`ref`/`reactive` 是存储字段，`computed` 是派生查询，`watch` 是变更时触发的回调。存、算、响，这条线讲完，Vue 里"数据怎么动起来"就通了。

## 一个容易踩的坑

两个新手最常见的报错，都来自对"盒子"理解不牢：一是 JavaScript 里漏写 `.value`，把盒子当成了值本身；二是把 `reactive` 对象解构了（`const { query } = form`），一旦拆开就断了响应。规避的办法很简单：简单值统一用 `ref`，别为了少敲一个 `.value` 把自己绕进去。

## 本节小结

- 响应式解决的是"数据变了界面要手动改"这件苦差：原来中间那根同步的线要你亲手牵，现在交给框架。
- `ref` 装单值、`reactive` 装对象，都是可观测的盒子，这正是 JavaScript 里要 `.value` 的由来。
- `computed` 声明派生值、带缓存；`watch` 挂载副作用、变则执行。先存、再算、后响，顺序不是随意的。
- 读一段 Vue 代码，先找数据（`ref`/`reactive`），再找派生（`computed`），最后找副作用（`watch`），三样齐了就懂了。

金句：响应式不是魔法，它只是把"数据一变界面就变"这件本该由人盯着的苦差，变成了框架替你盯着的默认行为。
