# 神经免疫 · Web 工作台（后端 + 前端）

把 `prototype/` 里的核心判断逻辑（杏仁核 / 黑板 / 前额叶 / 免疫耐受 / 固有免疫 / 夜间巩固）
包装成一个可实际值守的 Web 产品：FastAPI 后端复用 prototype 的 `amygdala`/`graph`/`system2`
等模块**一行不改**，只把 `main.py` 的批处理逻辑抽成可落库的管道（`pipeline.py`），React 前端做分诊工作台。

架构对应关系见根目录 `README.md`；本文件只讲**怎么把它跑起来**。

```
backend/   FastAPI 服务（:8000）—— REST API + 24h syslog 接收 + 定时夜间巩固
frontend/  React + Vite 单页应用（dev :5173，/api 代理到 :8000）
prototype/ 核心判断逻辑（被 backend 复用，模型配置也读这里的 .env）
```

---

## 一、依赖安装

```bash
# 后端（Python 3.11+）
cd backend
pip install -r requirements.txt

# 前端（Node 18+）
cd ../frontend
npm install
```

---

## 二、启动后端

```bash
cd backend
uvicorn app:app --reload --port 8000
```

启动即自动做三件事（见 `app.py`）：

1. **开 syslog 监听线程** —— UDP+TCP `:5514`，实时解析并增量入库；
2. **开夜间巩固线程** —— 每 `NEUROIMMUNE_CONSOLIDATE_INTERVAL` 秒（默认 6 小时）把当天案件蒸馏成记忆；
3. **建库** —— `neuroimmune.db`（SQLite，首次自动生成）。

> 生产部署去掉 `--reload`。端口被占用（如 5514）时 syslog 会打印一条「启动失败」但 API 照常可用——syslog 是可选的接入通道。

验证：`curl http://localhost:8000/api/health` 应返回 `{"status":"ok", ...}`（`/` 是精简健康检查，`/api/health` 是完整版）。

---

## 三、启动前端

```bash
cd frontend
npm run dev      # 开发模式：Vite 起在 :5173，/api 自动代理到 http://localhost:8000
```

浏览器打开 `http://localhost:5173`。六个页面：**看板 / 海马体 / 分诊队列 / 丘脑 / 免疫 / 设置**（+ 案件详情）。

**生产构建**（无 HMR，静态产出到 `dist/`）：

```bash
npm run build
```

`dist/` 是纯静态文件，`/api` 需反向代理到后端。示例（nginx）：

```nginx
location / { root /path/to/frontend/dist; try_files $uri /index.html; }
location /api/ { proxy_pass http://127.0.0.1:8000; }
```

> `vite preview` 默认**不会**代理 `/api`（它读 `preview.proxy`，项目只配了 `server.proxy`），所以本地预览请用 `npm run dev` 或上面的 nginx 方式。

---

## 四、配置（环境变量）

模型后端和 syslog 参数**统一在 `prototype/.env`** 里改（`llm.py` 会自动读取，只补缺、不覆盖已 export 的变量）：

| 变量 | 默认 | 作用 |
|---|---|---|
| `NEUROIMMUNE_API_KEY` | 空 | 杏仁核（初筛）模型的 key；**留空 = mock 模式**（零 key 先跑通架构） |
| `NEUROIMMUNE_BASE_URL` | `https://api.deepseek.com/v1` | OpenAI 兼容端点（DeepSeek / OpenRouter / Ollama / vLLM） |
| `NEUROIMMUNE_MODEL` | `deepseek-chat` | 杏仁核（便宜模型） |
| `NEUROIMMUNE_DEEP_MODEL` | `deepseek-reasoner` | 前额叶（贵模型，深想用；不想花钱换回 `deepseek-chat`） |
| `NEUROIMMUNE_SYSLOG_BIND` / `_PORT` | `0.0.0.0` / `5514` | syslog 接收地址 |
| `NEUROIMMUNE_CONSOLIDATE_INTERVAL` | `21600` | 夜间巩固间隔（秒） |
| `NEUROIMMUNE_API_TOKEN` | 空 | 可选共享 token；**设了则所有写操作（入库/处置/旋钮/清库）都要带 `X-API-Token`**，不设则本地免鉴权 |

---

## 五、鉴权（可选）

- 后端设 `NEUROIMMUNE_API_TOKEN` 后，写操作需要请求头 `X-API-Token: <token>`，否则 401。
- 前端会从 `localStorage` 读 `neuroimmune_token` 自动带上；本地用可在浏览器控制台设：
  `localStorage.setItem('neuroimmune_token', '<你的 token>')`。
- **本地开发建议不设 token**（默认免鉴权，最省事）；部署上线前再设。

---

## 六、数据落在哪

| 文件 | 内容 |
|---|---|
| `backend/neuroimmune.db` | SQLite：alerts / artifacts / cases / reports / audit_logs |
| `backend/knob.json` | 当前风险档位 |
| `backend/knob_presets.json` | 四档阈值覆盖（设置页改的就是它） |
| `backend/freq.json` | 频率降级参数（设置页保存后生成） |
| `backend/data/feedback.jsonl` | 处置反馈（供前额叶 RAG 检索误报经验） |
| `prototype/data/tolerance.json` | 免疫耐受白名单（跨运行累积） |
| `prototype/data/innate_rules.json` | 固有免疫规则（跨运行累积） |
| `prototype/data/memory.jsonl` | 夜间巩固沉淀的历史记忆 |

---

## 七、快速上手（5 分钟）

```bash
# 终端 1：后端（mock 模式，零 key）
cd backend && uvicorn app:app --port 8000

# 终端 2：前端
cd frontend && npm run dev

# 终端 3：数据接入——经 syslog（:5514）/ HTTP `/api/ingest` / Filebeat→Kafka 三通道（批量 CLI 已移除）
```

然后浏览器开 `http://localhost:5173`：看板有降噪漏斗，分诊队列有顶出案件，海马体能看到实体共现关系。点案件详情可「标记误报 / 真阳性」，规则回写进免疫耐受 / 固有免疫，下一轮自动生效（越用越准）。

---

## 八、关键设计说明（对照 README 六层）

| 层 | 后端落点 |
|---|---|
| 感知（杏仁核 + 抑制） | `pipeline.process_signal` → `amygdala.judge_signal`，低置信度抑制 + 完整留痕（`alerts.suppressed=1`，可「放回」） |
| 注意力（黑板） | 信号按实体反查归案 / 合并案件，`correlation_uid` 拼链 |
| 认知（杏仁核/前额叶） | 强度越 `escalate_above` 且预算内 → 后台线程跑 `system2.deep_analyze_chain`，带记忆 RAG |
| 响应（风险旋钮） | `state.get_knob`，四档阈值覆盖持久化，syslog 流式与 HTTP 入库读同一份 |
| 记忆（睡眠巩固） | `nightly.consolidate`：SQLite → `memory.jsonl`（供 RAG）+ 反馈 |
| 免疫（固有/耐受） | `innate` / `tolerance`，由分析师「标记真/误报」回写，跨运行累积 |

「频率降级」是抑制层的补丁：时间窗外历史同类型告警极多 → 判为业务误报并降级置信度，参数在设置页可调（默认 1 小时窗 / 10 次 / 折扣 0.4）。
