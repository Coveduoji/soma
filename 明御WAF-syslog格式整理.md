# 明御®Web 应用防火墙（WAF）V3.0R05 日志手册 —— syslog 外送日志格式整理

> 来源：《明御Web应用防火墙WAF-V3.0R05日志手册-02_104737.pdf》（文档版本 02，2025-07-16，安恒信息）
> 适用平台/版本：V3.0R05C45 及以后版本
> 日志外送支持 syslog 协议和邮件两种方式，本文只整理 **syslog 外送日志**。

WAF 的 syslog 外送日志分为 3 类：

| 序号 | 日志类型 | 输出格式 |
|------|----------|----------|
| 1 | 操作日志 | JSON（竖线分割 / JSON 两种，手册示例为 JSON） |
| 2 | 系统日志 | JSON |
| 3 | 应用防护日志 | 非 JSON：`Key/Value` 以 `/` 分隔，键值对之间以 `,` 分隔 |

所有 syslog 消息均带标准 syslog 头部：`<月> <日> <时:分:秒> <来源标识> <进程标识>`。

---

## 1. 操作日志（syslog 外送）

输出格式为 **JSON**。示例（新建站点操作）：

```
Mar 7 13:52:53 10.20.187.148 DBAppWAF: {"Event ID": "567", "Code": "0", "Timestamp": "2025-03-07 13:52:50+08:00", "Username": "admin", "Client IP": "10.11.33.123", "Device ID": "cbec8b60-4d58-538c-a7d7-c07b9b5d0ec0", "Target Name": "Create website", "Operate Type": "OPERATE", "Operate Result": "success", "Detail": {"extend": {...}, "req_body": {...}, "res_body": {...}, "params": [], "message": "success"}, "Event Level": "normal"}
```

### 字段说明

| 字段 | 字段含义 | 说明 |
|------|----------|------|
| Tag | 系统标识 | 用来标识系统，可自定义 |
| DBAppWAF | WAF 标识 | 固定值，不可修改 |
| Event ID | 事件 ID | 自增 |
| Code | 代码 | 操作日志，code 为 0 |
| Timestamp | 时间 | 日志产生的时间，格式 `YYYY-MM-DD HH:mm:ss+08:00` |
| Username | 用户名 | 操作用户名 |
| Client IP | 客户端 IP | 用户登录系统使用的 IP；当日志产生者为系统模块时，本项为空或 127.0.0.1 |
| Device ID | 设备 ID | WAF 设备 ID，固定值 |
| Target Name | 事件名称 | 比如删除站点、登录等 |
| Operate Type | 操作类型 | 比如：删除、操作（示例为 OPERATE） |
| Operate Result | 操作结果 | 该日志执行的操作结果（如 success） |
| Detail | 详情 | 详细描述该日志的内容 |
| Event Level | 事件等级 | normal：一般；medium：中等；critical：严重；serious：危急 |

---

## 2. 系统日志（syslog 外送）

输出格式为 **JSON**。示例（修改系统时间）：

```
Mar 7 14:20:30 WAF-148 DBAppWAF: {"Event ID": "228", "Code": "14004", "Timestamp": "2025-03-07 14:20:27+08:00", "Username": "log service", "Client IP": "10.20.187.148", "Device ID": "cbec8b60-4d58-538c-a7d7-c07b9b5d0ec0", "Target Name": "Modify system time", "Operate Type": "OPERATE", "Operate Result": "success", "Detail": {"msg": "Modify system time, Modification method: local", "extend": {}, "format": ["local"], "req_body": "", "res_body": "", "trans_params_index": []}, "Event Level": "normal", "Status": "2", "Unique Tag": "999eda5b9291be7024be8b51205c019b"}
```

### 字段说明

| 字段（英文） | 字段（中文） | 说明 |
|--------------|--------------|------|
| Tag | 系统标识 | 用来标识系统，可自定义，如 WAF_110 |
| DBAppWAF | WAF 标识 | 固定值，不可修改 |
| Event ID | 事件 ID | 自增 |
| Code | 代码 | 系统日志：code 值为 1-20000（与操作日志的 code=0 区分） |
| Timestamp | 时间 | 日志产生的时间，格式 `YYYY-MM-DD HH:mm:ss+08:00` |
| Username | 用户名 | 操作用户名（示例为 log service） |
| Client IP | 客户端 IP | 用户登录系统使用的 IP；当日志产生者为系统模块时，本项为空或 127.0.0.1 |
| Device ID | 设备 ID | WAF 设备 ID，固定值 |
| Target Name | 事件名称 | 比如：修改系统时间 |
| Operate Type | 操作类型 | 比如：操作（示例为 OPERATE） |
| Operate Result | 操作结果 | 该日志执行的操作结果（如 success） |
| Detail | 详情 | 详细描述该日志的内容 |
| Event Level | 事件等级 | normal：一般；medium：中等；critical：严重；serious：危急 |
| Status | 状态 | 0：未处理；1：已处理；2：无需处理 |
| Unique Tag | 唯一标识 | 系统日志唯一标识，日志参数变化标识也会变化 |

---

## 3. 应用防护日志（syslog 外送）

输出格式为 **非 JSON**：**key 和 value 间以 `/` 分割，不同的键值对之间以 `,` 分割**。

示例（URL 文件访问拦截）：

```
Jul 17 11:24:08 WAF WAF: Timestamp/2025-07-17 11:23:59,Threat Level/High,Event/URL File Access,Method/GET,Url/10.20.187.207:1111/login.mdb,Request Body/,Service IP/10.20.187.207,Host Name/10.20.187.207:1111,Service Port/1111,Client IP/113.121.12.134,Source Port/61670,UA/Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36,Tag/Generic Defence,Action/Deny,Server Response Code/0,Attack Signature/.mdb,Rule ID/10113000,Request ID/7527886413466959876,Country/CN,Province/SD,City/Yantai,XFF Header/113.121.12.134,Request Header/GET /login.mdb HTTP/1.1\r\nHost: ...\r\nCookie: ...,Action Detail/Blocked Using 403 Status code,Site name/111
```

### 字段说明

| 字段（英文） | 字段（中文） | 字段含义 |
|--------------|--------------|----------|
| Tag | — | 系统标识，用来标识系统，可自定义，如 10.20.187.148 |
| WAF | — | WAF 标识，固定值，不可修改 |
| Timestamp | 发送时间 | 日志产生的时间，格式 `YYYY-MM-DD HH:mm:ss` |
| Threat Level | 威胁等级 | 应用防护威胁等级（示例为 High） |
| Event | 事件 | 规则名称（示例为 URL File Access） |
| Method | 请求方法 | 攻击报文使用的请求方法：GET / POST / PUT / … |
| URL | URL 地址 | 完整 URL 地址 |
| Request Body | POST 数据 | 请求体内容，无请求体时为空 |
| Service IP | 服务器 IP | 访问的服务器 IP 地址。透明模式是服务器的真实地址，反代模式下为 WAF 代理地址 |
| Host Name | 主机名 | 域名 |
| Service Port | 服务器端口 | 访问服务器端口。透明模式是服务器的端口，反代模式下为 WAF 代理端口 |
| Client IP | 客户端 IP | 客户端 IP 地址 |
| Source Port | 客户端端口 | 客户端端口 |
| UA | 客户端环境 | 客户端 User-Agent 环境信息 |
| Tag | 标签 | 防护模块（示例为 Generic Defence） |
| Action | 动作 | 防护日志触发之后 WAF 的执行动作（示例为 Deny） |
| Response Code | HTTP/S 响应码 | 响应码（示例为 0） |
| Attack Signature | 攻击特征串 | 攻击特征（示例为 .mdb） |
| Rule ID | 触发规则 | 触发的规则 ID（示例为 10113000） |
| Request ID | 请求 ID | 应用防护日志的请求 ID |
| Country | 国家 | 客户端地理位置-国家 |
| Province | 省 | 客户端地理位置-省 |
| City | 市 | 客户端地理位置-市 |
| XFF Header | Xff_ip | XFF 地址 |
| Request Header | 请求头 | HTTP 请求信息 |
| Action Detail | 动作详情 | 防护日志触发之后 WAF 的具体动作详情（示例为 Blocked Using 403 Status code） |
| Site name | 站点名称 | 产生防护日志的所属保护站点名称 |

---

## 附：三格式对比速览

| 日志类型 | 消息体格式 | 分隔符 | 标识字段 | 特有字段 |
|----------|------------|--------|----------|----------|
| 操作日志 | JSON | — | DBAppWAF | Code=0 |
| 系统日志 | JSON | — | DBAppWAF | Code=1~20000；Status；Unique Tag |
| 应用防护日志 | Key/Value 平铺 | `/` 分隔键值、`,` 分隔键值对 | WAF | Threat Level / Event / Rule ID / Action / Request ID 等 |
