---
numbering: false
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# `__init__.py`：让目录变成包

在 `src` 布局中，你会看到每个子目录下都有一个 `__init__.py` 文件。新手容易忽略它，甚至觉得"空文件碍事"。但它是 Python 包机制的核心。

## 为什么需要 `__init__.py`

一个目录只有包含 `__init__.py`，Python 才会将其识别为**包（Package）**，才能被 `import` 语句导入。

```python
# 有 __init__.py 时
from src.core import config      # ✅ 可以导入

# 没有 __init__.py 时
import src.core.config           # ❌ ModuleNotFoundError
```

Python 3.3+ 引入了"命名空间包"（不含 `__init__.py` 的目录也可被导入），但这会带来风险：

- 多个同名目录可能意外合并成一个包
- 导入行为变得不可预测
- 无法控制包的初始化逻辑

**工程建议**：无论包结构多深，每个目录都放一个 `__init__.py`，即使是空文件。这是显式声明"这是一个包"的最可靠方式。

## 以 `core/__init__.py` 为例：从空文件到公共入口

### 基础版本（空文件）

```python
# src/src/core/__init__.py
# 空文件，仅仅标识 core 为 Python 包
```

空文件已经足够，让 `core/` 成为包，使得：
```python
from src.core import config       # ✅ 可以
from src.core.config import CONFIG  # ✅ 可以
```

### 进阶版本：控制导入便利性

```python
# src/src/core/__init__.py
from .config import Config, Settings
from .constants import APP_NAME, VERSION
from .database import Database, get_db

# 定义 __all__ 控制 from core import * 的行为
__all__ = [
    "Config",
    "Settings",
    "APP_NAME",
    "VERSION",
    "Database",
    "get_db",
]
```

这样使用者可以简化导入：
```python
# ✅ 简洁：从包层级直接导入
from src.core import Config, APP_NAME, Database

# ❌ 冗长：每次都要写完整路径
from src.core.config import Config
from src.core.constants import APP_NAME
from src.core.database import Database
```

这种做法的好处是：**包的内部结构可以随意调整，只要 `__init__.py` 中暴露的接口保持不变，使用者的代码就不需要修改**。这是一种"门面模式"（Facade Pattern）的体现。

### 高阶版本：包初始化与版本管理

```python
# src/src/core/__init__.py
import logging

# 1. 包级别的日志记录器
logger = logging.getLogger(__name__)

# 2. 包的版本号
__version__ = "0.1.0"

# 3. 控制公共 API
from .config import Config, Settings
from .constants import APP_NAME, VERSION
from .database import Database, get_db
from .exceptions import CoreError, ConfigError

__all__ = [
    "Config",
    "Settings",
    "APP_NAME",
    "VERSION",
    "Database",
    "get_db",
    "CoreError",
    "ConfigError",
    "logger",
]
```

使用者可以：
```python
from src.core import Config, CoreError, __version__

print(f"Using core v{__version__}")
```

## `__init__.py` 的常见用法总结

| 用法 | 示例代码 | 目的 |
|------|----------|------|
| **标识包** | 空文件 | 让 Python 识别目录为包 |
| **简化导入** | `from .config import Config` | 提供快捷导入路径 |
| **控制 `*` 导入** | `__all__ = ["Config", "Database"]` | 明确公共 API，隐藏内部实现 |
| **版本管理** | `__version__ = "0.1.0"` | 提供包的版本信息 |
| **包初始化** | `logger = logging.getLogger(__name__)` | 包导入时设置日志、注册插件等 |

## 最佳实践

**1. 空文件也要保留**

```python
# ✅ 推荐：即使是空文件，每个包目录都要有
# src/src/core/__init__.py （空）
```

**2. 不要在 `__init__.py` 中放重量级逻辑**

```python
# ❌ 避免：导入时执行耗时操作
import heavy_library  # 每次导入包都会加载
init_database()       # 副作用难以控制

# ✅ 推荐：仅做导入聚合，复杂逻辑留给子模块
from .config import Config
from .database import Database
```

**3. 用 `__all__` 明确公共 API**

```python
# ✅ 推荐：显式声明公开的内容
__all__ = [
    "Config",
    "Settings",
    "get_db",
]

# 未列出的内容视为包内部实现，使用者不应直接导入
from .internal import _internal_helper
```

**4. 内部导入优先使用相对路径**

```python
# ✅ 推荐：相对导入，不依赖包名
from .config import Config
from .database import Database

# ❌ 避免：绝对导入（包重命名时需要修改）
from src.core.config import Config
```

## 一个完整的 `__init__.py` 模板

你可以作为项目起步的参考：

```python
"""
src.core - 核心配置与基础设施

该包提供：
- 配置管理 (Config, Settings)
- 数据库连接 (Database, get_db)
- 公共常量 (APP_NAME, VERSION)
- 自定义异常 (CoreError, ConfigError)
"""

# 版本信息
__version__ = "0.1.0"

# 导入公共 API
from .config import Config, Settings
from .constants import APP_NAME, VERSION
from .database import Database, get_db
from .exceptions import CoreError, ConfigError

# 控制公共导出
__all__ = [
    "Config",
    "Settings",
    "APP_NAME",
    "VERSION",
    "Database",
    "get_db",
    "CoreError",
    "ConfigError",
]

# 包级别初始化（轻量级）
import logging
logger = logging.getLogger(__name__)
```

---

## 工程启示

`__init__.py` 不只是一种语法要求，它是一种**设计工具**：

- **封装**：隐藏包的内部结构，只暴露必要的 API
- **稳定**：内部文件可以随意重组，只要 `__init__.py` 的接口不变，使用者不受影响
- **自文档**：看一眼 `__init__.py`，就能知道这个包提供了什么功能

在 `src` 布局中，每个子包的 `__init__.py` 共同构成项目的**公共门面**。写好它们，项目就成功了一半。