# Soma · 最小闭环原型

README 3.2 节的最小闭环：**杏仁核 + 一块黑板**。先解决告警疲劳和工具烟囱两个最痛的问题，不推翻任何现有投资。

```
信号文件 ──► 耐受白名单(已知好→静默) ──► 固有免疫规则(已知坏→秒拦) ──► 杏仁核(判「不对劲」+ 置信度) ──► 抑制(低置信度静默) ──► 黑板(打分+拼链) ──► 顶出 ──► 前额叶(预算内深想)
   ▲                                                    ▲                                                                                    │
   └────────── 误报回写进白名单 ◄──────────────────────────────────────────────────────────── 睡眠巩固(夜里 consolidate.py) ◄──────────┘
                                                                                                             └──► 提炼 TTP 回写固有免疫规则 + 检索记忆库
```

## 跑起来

```bash
cd prototype
python3 main.py                       # 读内置样例 data/sample.jsonl（mock 模型，零 key）
python3 main.py --input alerts.jsonl   # 读你自己的告警导出
python3 main.py --knob 战时            # 换风险旋钮：宽松 / 正常 / 保守 / 战时
```

依赖只有 `httpx`（`pip install -r requirements.txt`）。

## 信号文件格式

支持 `.jsonl`（每行一条）、`.json`（顶层数组）、`.csv`（带表头）三种，每条信号统一五个字段：

| 字段 | 含义 |
|---|---|
| `time` | 时间戳 |
| `source` | 来源（身份/云/数据/流量/登录…） |
| `asset` | 关联主体（账号/主机/桶，拼链就靠它） |
| `type` | 类型（登录/身份/流量/导出/心跳…） |
| `raw` | 原始文本（杏仁核真正去读的那一段） |

真实 SIEM/EDR 导出字段对不上时，加一层字段映射即可（把导出列名重命名成这五个）。

## 接真实开源模型（OpenAI 兼容端点通用）

原型默认用 `MockClient`（规则版杏仁核）先跑通架构。拿到 key 后，**直接编辑 `prototype/.env`**（`llm.py` 会自动读取），即可无缝切换，上层代码一行不用改：

```bash
# prototype/.env 里，把 key 填进去即可：
SOMA_API_KEY=sk-xxx          # DeepSeek 的 key
SOMA_BASE_URL=https://api.deepseek.com/v1
SOMA_MODEL=deepseek-chat
```

`.env` 里还留了另外两组注释掉的备选：OpenRouter 免费开源模型、本地 Ollama，取消注释换一下即可。

`llm.py` 里 `OpenAICompatClient` 就是那层「大脑是胶水，不是模型」的胶水——换 provider 只改 `.env`。

## 文件 ↔ 架构层对应

| 文件 | 大脑对应 | 干的活 |
|---|---|---|
| `llm.py` | 模型入口（第0步） | 薄薄的调用封装：mock / OpenAI 兼容两种后端 |
| `amygdala.py` | 杏仁核 + 抑制（感知层） | 逐条判「不对劲」，产出置信度；低于阈值静默 |
| `blackboard.py` | 黑板 / 全局工作空间（注意力层） | 统一 schema、显著性打分、弱信号拼链、顶出 |
| `system2.py` | 前额叶（认知层） | 预算内唤醒贵模型深想：定性、重建攻击链、处置建议 |
| `config.py` | 风险旋钮（响应层） | 四档预设 → 抑制线 + 顶出线 + 深度算力预算三个旋钮 |
| `tolerance.py` | 免疫耐受（免疫层） | 误报回写白名单，跨运行持久化（`data/tolerance.json`） |
| `innate.py` | 固有免疫（免疫层） | 已知坏规则，边缘秒拦（`data/innate_rules.json`） |
| `consolidate.py` | 睡眠巩固（记忆层） | 夜里用贵模型整合一天事件 → 检索记忆 + 回写规则 |
| `visualize.py` | — | 把盘上状态渲染成自包含的 `report.html`（路由观测，不是告警大屏） |
| `syslog.py` | — | syslog 解析器（RFC3164 / RFC5424 → 统一信号） |
| `receiver.py` | — | 24h syslog 接收服务（UDP+TCP，实时喂管道） |
| `signals.py` | — | 信号加载器：从 `data/sample.jsonl`（或 `--input` 指定文件）读信号流 |
| `data/sample.jsonl` | — | Day1 样例（复刻巅峰场景的供应链投毒链） |
| `data/day2.jsonl` | — | Day2 样例（同家族新变种，验证固有免疫秒拦） |
| `main.py` | — | demo 驱动，串起整个闭环 |

## 杏仁核 / 前额叶 路由（已做）

杏仁核（便宜模型 `deepseek-chat`）先定性分级；只有越过黑板顶出线、且**预算没花完**的信号，才唤醒前额叶（贵模型 `deepseek-reasoner`）做深度分析。预算随风险旋钮走：宽松 1 / 正常 2 / 保守 3 / 战时 99（次/轮）。这就是「告警降噪」——贵模型醒在「那一条」上，不醒在九千九百九十九条上。

前额叶 的 `analyze()` 走 `llm.py` 同一个 OpenAI 兼容客户端，深想模型在 `.env` 里配 `SOMA_DEEP_MODEL`（不想花推理模型的钱就换成 `deepseek-chat`）。

## 免疫耐受回写（已做）

信号里可选 `label: "benign"` 字段，表示「分析师已确认这是正常业务」。每轮结束时，把这些信号的 `(asset, type)` 写进 `data/tolerance.json`；下一轮再遇到同 `(asset, type)` 的信号，直接静默——**连杏仁核都不用叫**。跨运行累积，越用越懂。

> 注：白名单按 `(asset, type)` 匹配是粗粒度（demo 简单）。真实落地要用更细的签名（raw 模式指纹），否则会漏掉同一资产上的真实攻击——这是免疫耐受的固有风险。

## 睡眠巩固 + 免疫记忆（已做）

`python3 consolidate.py` 是夜里的「睡眠巩固」任务：读当天 `data/history.jsonl`（`main.py` 每轮自动追加），用贵模型整合成结构化记忆，两个去向：

- **(a) 检索记忆库** `data/memory.jsonl`：跨天记住上下文（真实落地用向量库，这里 JSONL 简化）。
- **(b) 回写固有免疫** `data/innate_rules.json`：把被顶出且非误报的 `(asset, type)` 提炼成规则。下次同家族信号在边缘被秒拦，**杏仁核、前额叶 都不用醒**——正是巅峰场景里「两周后同一家族被固有免疫秒拦」的实现。

完整跑一遍看全貌：

```bash
python3 main.py                          # Day1：检出攻击链，写 history
python3 consolidate.py                   # 夜里：沉淀记忆 + 回写固有免疫规则
python3 main.py --input data/day2.jsonl  # Day2：新变种被固有免疫秒拦，前额叶 没醒
```

## 可视化（路由观测）

```bash
python3 main.py        # 产生一次运行 → data/last_run.json
python3 visualize.py   # 生成 report.html，浏览器直接打开
```

`report.html` 是自包含的静态页（内联 CSS、零依赖、零服务）。它**不是态势感知大屏**——只讲三件事：**省**（漏斗：信号 → 上板 → 顶出 → 唤醒前额叶）、**学**（耐受白名单 + 固有免疫规则 + 检索记忆）、**调**（风险旋钮四档）。守住 README「黑板是路由决策点，不是展示屏」的红线。

## 24h syslog 接收（receiver.py）

```bash
python3 receiver.py                       # 默认 UDP+TCP :5514，正常档，60s 窗口
python3 receiver.py --port 5514 --knob 保守 --window 30
```

常驻服务，Ctrl+C 退出。UDP + TCP 双监听，每条立即判（耐受 → 固有免疫 → 杏仁核 → 黑板），
每 window 秒顶出一次 + 唤醒前额叶 深想 + 写 `history.jsonl`（夜里 `consolidate.py` 读它回写规则）。
端口/绑定/窗口也可用环境变量 `SOMA_SYSLOG_PORT/BIND/WINDOW` 配（见 `.env`）。

**测试**（另开一个终端）：

```bash
logger -n 127.0.0.1 -P 5514 "svc_backup 服务账号凌晨登录 payroll-db-05"     # UDP
echo '<34>1 2026-08-14T03:14:07Z web-01 auth 123 - - Failed password' | nc 127.0.0.1 5514  # TCP
```

**接 rsyslog 转发**：在 `/etc/rsyslog.d/99-soma.conf` 加一行 `*.* @127.0.0.1:5514`（UDP）或 `*.* @@127.0.0.1:5514`（TCP），重启 rsyslog。

**字段映射**（syslog → 信号）：

| 信号字段 | 来自 syslog |
|---|---|
| `time` | 时间戳（RFC5424 ISO 或 RFC3164 `Mmm dd hh:mm:ss`） |
| `source` | facility 中文归类（auth→认证、cron→计划任务、daemon→系统服务…） |
| `asset` | 主机名（拼链的关联主体） |
| `type` | facility 原文（`auth`/`cron`…，拼链用同主机+同 facility） |
| `raw` | 消息正文（杏仁核读的那段） |

> 注：syslog 的 `asset`=主机名、`type`=facility，跟批处理样例里 `asset`=账号、`type`=中文类型不同。
> 所以耐受/固有免疫规则是**按数据源各自累积**的——接 syslog 后要跑 `consolidate.py` 重新提炼规则。

## 当前边界（有意没做的）

- **不是大屏**：黑板只输出「顶出名单」，不画图不做可视化——README 死守的红线。
- **信号还是样例数据**：`data/*.jsonl` 是复刻巅峰场景的样例，换真实导出只要 `--input` 指过去、字段对上即可。
- **阈值未校准**：0.55/0.75 是按 mock 的置信度区间手调的，真模型的置信度聚集在 0.7~0.95，得拿真实数据重新标定。
- **记忆库是 JSONL 简化版**：README 里的「向量库」这里用 `memory.jsonl` 替代，没做语义检索。

## 下一步建议顺序

1. 拿一份真实告警导出（JSONL/CSV），`--input` 指过去跑通；字段对不上就加一层映射。
2. 校准阈值：拿真实数据把 0.55/0.75 两个阈值调准。
3. 检索记忆库换向量检索（embedding + 相似度），替代现在 JSONL 的 grep。
