"""薄薄的模型调用封装。

核心原则（README「大脑是胶水，不是模型」）：模型随便换，这里只负责
「输入 → 输出」，不关心上层怎么编排。两个入口：
- judge()：杏仁核/系统1 用，输出 JSON 判定
- analyze()：系统2 用，输出自由文本的深度分析

默认 MockClient：零 key、零网络也能跑通整个闭环；
设了 NEUROIMMUNE_API_KEY 就切到 OpenAI 兼容的开源模型 API。
"""
from __future__ import annotations

import json
import os
import threading

import httpx

# 杏仁核只判一件事，prompt 刻意收窄（README：便宜的模型要「专门」）。
JUDGE_SYSTEM = (
    "你是一个安全检测模块「杏仁核」，只做一件事：评估一条信号的可疑程度。"
    "只输出一个 JSON 对象，不要输出任何其他文字，字段如下：\n"
    "suspicious: 布尔值，true=可疑、值得进一步分析，false=正常。\n"
    "confidence: 0到1的浮点数，表示「这条信号是异常/可疑」的程度，越高越可疑。"
    "注意它衡量的是可疑程度，不是「我对判断的把握」。正常业务（正常登录、心跳正常、流量平稳）"
    "必须给接近 0 的低分，只有确实可疑才给高分。\n"
    "reason: 一句话中文理由。"
)


def _assets_context(signal: dict) -> str:
    """从解析前置已标注的 entities 里提取「涉及我方资产」段落，供杏仁核研判参考。"""
    ents = signal.get("entities") or []
    ours = [e for e in ents if e.get("role")]
    if not ours:
        return "\n\n涉及我方资产：无（信号中的 IP/域名均为外部）"
    lines = [
        f"{e.get('type')} {e.get('value')} → {e.get('role')}（敏感度 {e.get('criticality', 'normal')}）"
        for e in ours
    ]
    return "\n\n涉及我方资产（这些 IP/网段/域名是我们自己的，从它们发起的出网通常是正常的）：\n" + "\n".join(lines)


def _judge_prompt(signal: dict) -> str:
    return JUDGE_SYSTEM + _assets_context(signal) + "\n\n信号内容：\n" + json.dumps(signal, ensure_ascii=False)


class ModelClient:
    """基类：judge() 给杏仁核/系统1 用，analyze() 给系统2 深想用。"""

    def judge(self, signal: dict) -> str:
        raise NotImplementedError

    def analyze(self, prompt: str) -> str:
        raise NotImplementedError


def _env_http_proxy() -> str | None:
    """取一个 http/https 类型的代理。

    httpx 遇到 socks:// 的 ALL_PROXY 会直接抛错（它只认 socks5://），
    所以这里只认 http(s) 代理，忽略 socks——我们的请求全是 https，走 HTTPS_PROXY 即可。
    """
    for name in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        val = os.environ.get(name, "").strip()
        if val.startswith(("http://", "https://")):
            return val
    return None


class OpenAICompatClient(ModelClient):
    """任何 OpenAI 兼容端点通用：DeepSeek / OpenRouter / Groq / Ollama / vLLM。

    temperature=None 表示不发送该参数（推理模型如 deepseek-reasoner 不支持）。

    httpx.Client 作为实例持有（连接池复用，跨请求保活），不再每条请求新建连接。
    并发上限由 semaphore 限制、连接池大小由 max_connections 限制——两者应一致
    （都等于配置的并发数，见 backend/state.py）。
    """

    def __init__(self, base_url: str, api_key: str, model: str, temperature: float | None = 0.0,
                 timeout: float = 120.0, max_connections: int = 1,
                 semaphore: threading.BoundedSemaphore | None = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.timeout = timeout
        self.semaphore = semaphore
        limits = httpx.Limits(max_connections=max_connections,
                              max_keepalive_connections=max_connections)
        # 显式指定代理，避免 httpx 去解析 socks:// 的 ALL_PROXY 而崩掉。
        # 注意 httpx 0.28 起用单数 proxy=，且是 Client 的参数，故显式构造 Client。
        proxy = _env_http_proxy()
        if proxy:
            self._client = httpx.Client(proxy=proxy, timeout=timeout, limits=limits)
        else:
            self._client = httpx.Client(trust_env=False, timeout=timeout, limits=limits)

    def _post(self, content: str) -> str:
        payload: dict = {
            "model": self.model,
            "messages": [{"role": "user", "content": content}],
            "stream": False,  # 显式非流式：部分网关（Higress）默认流式，不带该字段会返回 SSE 导致 json() 解析失败
        }
        if self.temperature is not None:
            payload["temperature"] = self.temperature
        if self.semaphore is not None:
            self.semaphore.acquire()
        try:
            resp = self._client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        finally:
            if self.semaphore is not None:
                self.semaphore.release()

    def judge(self, signal: dict) -> str:
        return self._post(_judge_prompt(signal))

    def analyze(self, prompt: str) -> str:
        return self._post(prompt)


# 可疑关键词 -> 权重。mock 版杏仁核的「规则初筛」
# （README 1.2：规则 + 嵌入异常做初筛，只有初筛命中才让模型看一眼）。
_INDICATORS = [
    ("svc_backup", 0.18), ("服务账号", 0.16), ("三个月没碰", 0.15),
    ("mfa", 0.18), ("绕过", 0.20), ("bypass", 0.20),
    ("陌生", 0.15), ("oss", 0.12),
    ("批量导出", 0.18), ("晚跑", 0.12), ("导出", 0.08),
    ("权限变更", 0.18), ("异常登录", 0.18),
    ("供应链", 0.20), ("投毒", 0.22),
]
# 对外暴露的默认关键词表（Web 设置页 mock 规则的默认值）
DEFAULT_INDICATORS = _INDICATORS


class MockClient(ModelClient):
    """规则版杏仁核：用关键词权重模拟便宜模型，无 key 也能跑。

    indicators/no_hit/base/ceiling/cutoff 均可注入（Web 设置页可调 mock 规则）。
    """

    def __init__(self, indicators=None, no_hit: float = 0.15, base: float = 0.32,
                 ceiling: float = 0.72, cutoff: float = 0.5):
        self.indicators = list(indicators) if indicators is not None else _INDICATORS
        self.no_hit = no_hit
        self.base = base
        self.ceiling = ceiling
        self.cutoff = cutoff

    def judge(self, signal: dict) -> str:
        text = json.dumps(signal, ensure_ascii=False).lower()
        hits = [(kw, w) for kw, w in self.indicators if kw in text]
        if not hits:
            return json.dumps(
                {"suspicious": False, "confidence": self.no_hit, "reason": "未命中任何可疑特征"},
                ensure_ascii=False,
            )
        # 弱信号：单条命中也不轻易给高分，留给黑板去「拼链」抬轿。
        confidence = min(self.ceiling, self.base + sum(w for _, w in hits))
        reason = "命中特征：" + "、".join(kw for kw, _ in hits)
        return json.dumps(
            {"suspicious": confidence >= self.cutoff, "confidence": confidence, "reason": reason},
            ensure_ascii=False,
        )

    def analyze(self, prompt: str) -> str:
        return json.dumps({
            "verdict": "Suspicious", "confidence": "Medium",
            "digest": "（mock）该案件可疑，建议人工复核。",
            "evidence": [], "attack_chain": [], "iocs": [], "unknowns": [], "remediations": [],
        }, ensure_ascii=False)


def load_dotenv(path: str | None = None) -> None:
    """极简 .env 读取：只补缺，不覆盖已存在的环境变量（与 python-dotenv 默认一致）。

    默认读 prototype/.env，所以直接编辑那个文件即可，不用手动 export。
    """
    if path is None:
        path = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val


def get_client() -> ModelClient:
    """系统1（便宜模型）：先读 prototype/.env 再选后端；没设 key 就退回 mock。"""
    load_dotenv()
    if os.environ.get("NEUROIMMUNE_MOCK") == "1":
        return MockClient()
    key = os.environ.get("NEUROIMMUNE_API_KEY", "").strip()
    if key:
        return OpenAICompatClient(
            base_url=os.environ.get("NEUROIMMUNE_BASE_URL", "https://api.deepseek.com/v1"),
            api_key=key,
            model=os.environ.get("NEUROIMMUNE_MODEL", "deepseek-chat"),
        )
    return MockClient()


def get_deep_client() -> ModelClient:
    """系统2（贵模型）：默认 deepseek-reasoner，可被 .env 覆盖。没 key 时退回 mock。"""
    load_dotenv()
    if os.environ.get("NEUROIMMUNE_MOCK") == "1":
        return MockClient()
    key = (os.environ.get("NEUROIMMUNE_DEEP_API_KEY")
           or os.environ.get("NEUROIMMUNE_API_KEY", "")).strip()
    if key:
        return OpenAICompatClient(
            base_url=os.environ.get("NEUROIMMUNE_DEEP_BASE_URL")
            or os.environ.get("NEUROIMMUNE_BASE_URL", "https://api.deepseek.com/v1"),
            api_key=key,
            model=os.environ.get("NEUROIMMUNE_DEEP_MODEL", "deepseek-reasoner"),
            temperature=None,  # 推理模型不支持 temperature
        )
    return MockClient()
