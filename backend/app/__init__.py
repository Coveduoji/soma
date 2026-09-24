"""Soma后端应用包。

统一把 prototype/ 领域层（杏仁核/黑板/图/系统2/免疫/签名/LLM/配置）加入 sys.path，
供 app.services.* 直接 `import config / llm / amygdala` 等复用核心算法（一行不改）。
"""
from __future__ import annotations

import sys
from pathlib import Path

_PROTO = str(Path(__file__).resolve().parent.parent.parent / "prototype")
if _PROTO not in sys.path:
    sys.path.insert(0, _PROTO)
