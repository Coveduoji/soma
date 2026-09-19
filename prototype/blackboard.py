"""黑板 / 全局工作空间（注意力层）——README 反复强调：它是路由决策点，不是展示大屏。

统一 schema，把所有上板的信号聚到一起；「竞争」= 显著性打分：单条置信度 +
与板上其他信号的关联度。两个弱信号能因为同资产/同类型拼成一条攻击链。
分高的往下走（唤醒系统2），其余静默。
"""
from __future__ import annotations

from dataclasses import dataclass, field

BOOST_SAME_ASSET = 0.15
BOOST_SAME_TYPE = 0.10
BOOST_CAP = 0.30  # 关联加成封顶，避免无脑堆叠


@dataclass
class Event:
    time: str
    source: str
    asset: str   # 关联主体（可能是账号/主机/桶，统一叫 asset）
    etype: str
    confidence: float
    raw: str
    reason: str
    label: str = ""  # 可选 ground-truth："benign"=已确认误报（免疫耐受回写用）
    innate: bool = False  # 固有免疫秒拦命中（已知家族，系统2无需再深想）
    entities: list = field(default_factory=list)  # 富化后的实体 [{type,value,role,criticality}]
    risk: float = 0.0  # 风险分（资产价值 × 攻击得逞 × 危害）
    risk_incomplete: bool = False  # 风险信息是否不全（缺攻击结果/威胁等级）


@dataclass
class Escalated:
    event: Event
    significance: float
    boost: float  # 关联加成（拼链抬轿了多少）


@dataclass
class Blackboard:
    events: list[Event] = field(default_factory=list)

    def post(self, event: Event) -> None:
        self.events.append(event)

    def boost(self, event: Event) -> float:
        """同资产/同类型的其他信号给这条抬多少轿（封顶 BOOST_CAP）。"""
        b = 0.0
        for other in self.events:
            if other is event:
                continue
            if other.asset == event.asset:
                b += BOOST_SAME_ASSET
            if other.etype == event.etype:
                b += BOOST_SAME_TYPE
        return min(b, BOOST_CAP)

    def significance(self, event: Event) -> float:
        """单条置信度 + 关联加成。"""
        return event.confidence + self.boost(event)

    def escalate(self, threshold: float) -> list[Escalated]:
        """只把显著性达标的「顶出」，按显著性降序——这就是唤醒系统2的名单。"""
        scored = sorted(
            (Escalated(e, self.significance(e), self.boost(e)) for e in self.events),
            key=lambda s: s.significance,
            reverse=True,
        )
        return [s for s in scored if s.significance >= threshold]

    def trim(self, max_events: int) -> None:
        """滚动裁剪，只保留最近 max_events 条（24h 常驻时避免无限增长）。"""
        excess = len(self.events) - max_events
        if excess > 0:
            del self.events[:excess]
