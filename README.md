# Soma

一个把 **神经系统 + 免疫系统** 的隐喻映射到 **SOC 告警降噪与研判** 的工作台。

核心思路：用「杏仁核（快、便宜）→ 前额叶（慢、贵）」的双层模型 + 「固有免疫 / 免疫耐受」两套确定性规则，把海量告警层层压缩成少数需要人工研判的**案件**，并在每一步决策都留下可审计的痕迹。

> 无需任何模型 API key 也能跑通全流程——内置 `MockClient` 用关键词规则替代 LLM，先把架构跑起来。

---

## 项目简介

项目自带「生物术语 / 安全术语」双术语体系（前端可一键切换），下表是隐喻到真实功能的映射：

| 生物/神经术语 | 安全术语 | 实际功能 |
|---|---|---|
| 丘脑 Thalamus | 原始告警 | 原始告警流视图（含被抑制项 + 抑制原因） |
| 海马体 Hippocampus | 关联分析 | 全局实体关系图 + 事件下钻 |
| 杏仁核 Amygdala | 初筛模型 | 对单条告警快速打分（可疑/置信度/理由） |
| 前额叶 / 系统2 System2 | 深度分析模型 | 对升级案件做结构化深度研判报告 |
| 黑板 Blackboard | 全局工作区 | 统一 Event 模型 + 显著性/相关性加权 |
| 固有免疫 Innate | 检测规则（黑名单） | 已知坏签名 → 置信度 0.95 秒拦，不调模型 |
| 免疫耐受 Tolerance | 白名单 | 已知好签名 → 静默抑制（降级不丢弃） |
| 签名 Signature | 告警形状 | 掩码 IP/hash/数字，提取稳定的告警模板 |
| 神经调质 Knob | 风险等级 | 风险预设，映射到抑制线/顶出线/预算 |
| 睡眠巩固 Consolidate | 夜间记忆固化 | 定期蒸馏当日案件为可检索记忆 |

一条告警的完整旅程：**免疫耐受（白名单静默）→ 固有免疫（黑名单秒拦）→ 杏仁核（快模型打分）→ 黑板（相关性加权）→ 实体图（连通分量 = 案件）→ 前额叶（深度研判出报告）→ 分析师判定（误报写回白名单 / 真阳写回黑名单）**。夜里「睡眠巩固」再把当天案件蒸馏成可检索记忆（供系统2 RAG），不回写免疫规则。

设计原则：**抑制 = 降级 + 留痕，永不静默丢弃**——每条被压掉的告警都能在「丘脑」页看到原因，必要时一键「放回」。

**亮点：AI 辅助接入新数据源。** 每家安全设备的 syslog 格式都不一样（天眼 `|!` 分隔、明御 WAF `key/value`、…），传统做法是每接一个设备手写一个解析器。这里反了过来——在「高级设置 → 数据接入」粘几条样本日志，内置深想模型**自动生成解析规则**（定长分隔 / 键值对 + 字段映射），人工确认后**实时保存、即时生效**（不用改代码、不用重启后端）。运行时走**确定性解析**（快、准、零模型成本），产出**精确实体**（源/目的 IP、hash、域名）直接喂给拼链，避免正则把版本号、UA 里的数字误当 IP。

---

## 快速开始

### 一键启动（开发）

```bash
./start.sh
```

自动装依赖 → 起后端 `:8000` → 起前端 `:5173`，日志写入 `logs/`，syslog 接收器监听 `:5514`（UDP+TCP）。启动后访问 http://localhost:5173 ，默认管理员 **`admin` / `admin`**（生产请用环境变量覆盖）。

```bash
BACKEND_PORT=8010 FRONTEND_PORT=5174 ./start.sh   # 自定义端口
```

### 手动启动

```bash
# 后端（先执行数据库迁移，再启动）
cd backend && alembic upgrade head && python3 -m uvicorn app.main:app --port 8000

# 前端（另开终端）
cd frontend && npm install && npm run dev
```

### 容器化部署（生产推荐）

```bash
cp .env.example .env      # 填 SOMA_ADMIN_PASSWORD / SOMA_API_TOKEN
docker compose up -d --build
```

- nginx 托管前端静态 + 反代 `/api`（默认 80 端口，HTTPS 见 `nginx.conf` 注释）。
- 数据持久化在命名卷 `soma-data`；备份/恢复：`./scripts/backup.sh` / `./scripts/restore.sh`。
- 安全底线：未设管理员凭据时**拒绝启动**；`/api/ingest` 未配 token 时**拒绝接入**；syslog 默认只绑 `127.0.0.1`。

### 纯内网离线部署

在能上网的机器上打包，拷入无网络的服务器：

```bash
./scripts/offline_bundle.sh            # Docker 方案：镜像 tar.gz → 内网 docker load
./scripts/offline_bundle_no_docker.sh  # 无 Docker 方案：wheel + dist + 源码 + systemd 单元
```

### 配置模型（可选）

复制 `prototype/.env.example` 为 `prototype/.env` 并填 key（`llm.py` 自动读取；留空 = mock 模式）：

| 变量 | 说明 | 默认 |
|---|---|---|
| `SOMA_API_KEY` | 系统1 模型 key | 空 = mock |
| `SOMA_BASE_URL` | OpenAI 兼容端点 | `https://api.deepseek.com/v1` |
| `SOMA_MODEL` | 系统1 模型名 | `deepseek-chat` |
| `SOMA_DEEP_MODEL` | 系统2（前额叶/深想）模型名 | `deepseek-reasoner` |

---

## 页面及功能介绍

| 页面 | 功能 |
|---|---|
| 看板 Dashboard | KPI 卡片、降噪率漏斗、24h/7d/30d 流量趋势、报告导出 |
| 分诊 Triage | 案件队列、状态/判定/强度过滤、批量标记误报 |
| 案件详情 CaseDetail | 攻击链 + 告警时间线 + 实体图（双向高亮）+ AI 报告 + 处置操作 |
| 丘脑 Thalamus | 原始告警流（含被抑制项）、决策留痕侧栏、一键放回 |
| 免疫 Immune | 白名单（免疫耐受）/ 检测规则（固有免疫）库管理 |
| 海马体 Hippocampus | 全局实体关联图（cytoscape）+ 逐节点/边事件下钻 |
| 设置 Settings | 风险旋钮预设、模型模式（auto/real/mock）、数据接入、健康状态、术语切换 |
| 高级设置 AdvancedSettings | 阈值四档、模型接入、频率降级、唤醒门控、检测调参、syslog、来源映射、来源解析（AI 生成）、webhook |
| 用户 Users | 修改密码；管理员用户管理 + 细粒度权限 |

### 权限模型

- 认证：JWT（HS256，24h）+ bcrypt 密码哈希；角色 `admin` / `user`，admin 隐式全权限。
- 四类细粒度权限：`triage`（分诊）· `config`（配置）· `maintenance`（维护）· `users`（用户管理）。
