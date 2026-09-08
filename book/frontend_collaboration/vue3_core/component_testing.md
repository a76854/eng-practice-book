---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# 组件测试

学完本节，你能回答：

- 改完一个组件，为什么要靠自动化测试而不是手动打开页面点一遍？
- Vitest 的 `describe` / `it` / `expect` 三个词各自做什么？
- `@vue/test-utils` 的 `mount` 如何测"组件渲染出了什么"、"交互发出了什么"？
- 组件测试、组合函数测试、端到端测试分别落在什么位置？

前面几节把 Vue 的模板、响应式、组件、路由、状态逐个讲完，天气应用也从一个 `WeatherCard` 长到了带路由和状态库的完整页面。但代码越堆越高，一个问题浮了上来：改一处组件，凭什么相信没把别处改坏？这一节给前端补上最后一块拼图，测试。

> 前端的手动验证像试衣服，每改一版都要重新往身上套一遍，穿好了还得对着镜子转一圈。组件测试像裁缝的样板纸：尺寸对不对、领口歪不歪，往样板上一对就知道，不用每次都找真人试。

后端接口怎么测，[第 4 章的接口测试](../../backend_development/http_restful/api_testing.md)讲过，套路是"断言行为 + 替换依赖"。前端组件测试是同一套思路换了对象：不再测"接口返回了什么"，而是测"组件渲染了什么、交互发出了什么"。这一节从最简单的纯函数起步，一路讲到组件渲染与交互。

## 为什么手动点一遍不够

改完组件，最省事的验证是启动 dev server、打开页面、点几下、看两眼。它确实能发现问题，但有两个天花板：一是**慢**，每次改动都要等构建、点页面；二是**不完整**，你只会点自己改过的那条路径，"加载中""出错"这些边角分支永远没人点。自动化组件测试补的就是这两个洞：快，且每条分支都能写一条断言、永远会被跑。

## Vitest 起步：先测一个纯函数

翻回"数据如何驱动视图"那一节，`computed` 把摄氏温度换成华氏。这种纯函数是测试最好的起点，先摸清 Vitest 的骨架：

```javascript
// src/utils/temperature.js
export function toFahrenheit(celsius) {
  return Math.round(celsius * 9 / 5 + 32)
}
```

```javascript
// src/utils/temperature.test.js
import { describe, it, expect } from 'vitest'
import { toFahrenheit } from './temperature.js'

describe('toFahrenheit', () => {
  it('摄氏转华氏', () => {
    expect(toFahrenheit(0)).toBe(32)
    expect(toFahrenheit(12)).toBe(54)
  })
})
```

`describe` 圈出一组相关用例，`it` 写一条具体的断言，`expect(...).toBe(...)` 判定结果。这和 pytest 的 `def test_xxx` 加 `assert` 是同一套心智，只是换成了 JavaScript 的表达。

## 组件测试：渲染与交互

纯函数好测，但前端真正要守住的是组件。`@vue/test-utils` 提供 `mount`，把一个组件"挂"到隔离的测试环境里，不碰真实浏览器。天气卡片 `WeatherCard` 只认一个 `weather` 属性往下渲染，测它渲染出了什么：

```javascript
// src/components/WeatherCard.test.js
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import WeatherCard from './WeatherCard.vue'

describe('WeatherCard', () => {
  it('把 weather 字段渲染进页面', () => {
    const wrapper = mount(WeatherCard, {
      props: { weather: { city: '北京', temperature: 12, condition: '晴' } }
    })
    const text = wrapper.text()
    expect(text).toContain('城市：北京')
    expect(text).toContain('温度：12°C')
    expect(text).toContain('天气：晴')
  })
})
```

`mount` 返回一个 `wrapper`，`wrapper.text()` 拿到渲染后的全部文本，`toContain` 断言它包含了该有的字段。这测的是"渲染"这一侧。

另一端是"交互"。`WeatherDatePicker` 不自己改状态，而是发 `update:date` 事件通知父组件。测它交互后发出了什么：

```javascript
// src/components/WeatherDatePicker.test.js
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import WeatherDatePicker from './WeatherDatePicker.vue'

describe('WeatherDatePicker', () => {
  it('改动日期时发出 update:date 事件', async () => {
    const wrapper = mount(WeatherDatePicker, { props: { date: '2024-01-15' } })
    const input = wrapper.find('input')
    await input.setValue('2024-01-16')
    expect(wrapper.emitted('update:date')).toBeTruthy()
    expect(wrapper.emitted('update:date')[0]).toEqual(['2024-01-16'])
  })
})
```

`find('input')` 定位到日期框，`setValue` 模拟用户输入，`emitted('update:date')` 取出这个组件发出去的事件。渲染测"长什么样"，交互测"做了会怎样"，两条合起来就是组件测试的主干。

```bash
# 安装测试工具，再跑一遍整条测试
npm i -D vitest @vue/test-utils
npx vitest run
```

## 再往上一级：组合函数与端到端

组合函数是纯逻辑，比组件还好测。跨组件状态那一节的 store 里，`loadWeather` 会真的发 `fetch` 请求，测试时不能让测试去连真接口，就用 Vitest 的 mock 把全局 `fetch` 换成假实现，断言它"换了日期会重新请求、请求成功会写入 weather"。套路不变：替换依赖、断言行为，和第 4 章接口测试的 `dependency_overrides` 异曲同工。

组件测试之外还有端到端测试，用 Playwright 在真实浏览器里把整条链路点一遍，第 8 章的天气样例里就带了一个 `screenshot.mjs` 做原型。它最慢、最接近真实用户，但跨前端的整链验证属于联调环节，这里点到为止。

## 本节小结

- 手动点一遍慢且不完整，自动化测试用"快 + 每条分支都被断言"补上这两个洞。
- Vitest 的 `describe` / `it` / `expect` 对应组织、断言、判定三步，和 pytest 是一套心智。
- `mount` 挂起组件，`wrapper.text()` 测渲染、`emitted()` 测交互，两条构成组件测试主干。
- 上游测纯函数与组合函数，下游测端到端，组件测试守中间这一段，各司其职。

金句：组件测试不是给组件挑刺，是给改组件的人发一张安全网。