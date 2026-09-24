# Soma · 当前进展

> 截至 2026-08-28：架构已从设计文档落地为可运行的产品雏形（原型 + Web 工作台）；syslog 接收链路（UDP/TCP + 来源映射）已端到端验证。

## 已落地

### 核心管道（`prototype/` + `backend/`）

- **杏仁核 + 抑制**：mock（关键词规则）与真实模型（OpenAI 兼容）双后端，`llm.py` 统一封装。
- **黑板 / 拼链**：实体抽取（IP/哈希/域名/标识符）+ 连通分量归案。
- **认知路由（前额叶唤醒）**：滑动窗口预算 + 单信号门槛，真实模型下 41 次误唤醒压到 1 次。
- **睡眠巩固**：`nightly.py` 夜里蒸馏案件 → 记忆库 + 反馈。
- **24h syslog 值守**：UDP+TCP 监听，实时增量入库。已端到端验证：RFC3164/RFC5424 双格式、来源映射优先级 `ip > tag > hostname > facility`、跨容器 src_ip 捕获命中 `ip` 映射（如 `2.3.4.5 → HIDS`）。

### 免疫层（签名匹配）

- **免疫耐受 + 固有免疫**：从粗粒度 `(asset, type)` 升级为**签名匹配**（掩码 IP/哈希/数字的告警形状，借鉴日志模板抽取 Drain/Spell），同一资产不同目标不再误静默。

### Web 工作台（`frontend/`）

- 看板（总览 + 8 项统计）、分诊队列、海马体（实体关系图）、丘脑（原始信号流）、免疫（白名单/规则，可删/清空）、设置（基础 + 高级）。
- **术语切换**：生物术语 ↔ 安全术语一键切换。
- **横向攻击链**：案件详情顶部把告警按时间串成 kill chain。

### 配置体系

- 风险旋钮（四档）、模型模式（auto/mock/real）、阈值、频率降级、前额叶唤醒门槛、Mock 规则、syslog 接入、来源映射——全部进设置页可配，持久化到 JSON，env 作 fallback。
- **来源映射迁到数据目录**：`syslog_sources.json` 权威文件从 `prototype/` 迁到数据目录（`backend/`，Docker 下 `/data` 卷），首启从种子自动播种；`prototype/` 那份仅作种子。
- **syslog bind 修复**：接入配置 bind 曾误设为非本机地址 `1.2.3.4`（重启会 bind 失败、监听静默丢失，`app.py` 只 warn 不报错），已改回 `0.0.0.0`；改 bind/port 需重启后端（socket 已绑定）。

### 测试数据

- `gen_attack_data.py`：生成 1000 条多设备真 log 格式告警，内嵌一条 SSRF → 内网 → 提权 → 横向 → 数据外带 攻击链；mock 回归 `1000 → 13 上板 → 7 案件 → 1 顶出`。
- syslog 接收测试：本机 socket 直发 + 固定 IP 容器发 UDP 验 ip 映射。容器用 `curl` 走代理下载 alpine minirootfs 再 `docker import`（绕开 daemon 直连 registry 超时），`docker run --ip 2.3.4.5` 发日志命中 `ip` 映射。

## 待办（`prototype/ROADMAP.md` 四）

- 案件实体图链式视图（可选）：案件详情改成按攻击阶段时序的 kill-chain 视图。
- 免疫签名相似度匹配（可选进阶：Jaccard/SimHash/embedding）。
- 免疫签名掩码粒度可配。

## 暂缓（`prototype/ROADMAP.md` 三）

- 置信度校准（命门，上线前必做）。
- 多租户共享情报 / 向量记忆。
