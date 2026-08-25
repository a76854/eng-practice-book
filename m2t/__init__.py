"""m2t 教学辅助包。

为什么存在：全书以「增量重建 MeetingToText」为主线，重复的样板（音频读
取、ASR 结果归一、LLM 调用、SQLite 存取、导出）若散落在每章会喧宾夺主。
本包把这些样板收敛到一处、保持精简，让正文只聚焦当章要讲的概念；同
时对外暴露稳定签名，方便习题与里程碑复用。
"""

from __future__ import annotations

__version__ = "0.1.0"
__all__ = ["__version__"]
