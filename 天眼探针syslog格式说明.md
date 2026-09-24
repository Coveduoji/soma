# syslog格式说明

## Syslog格式说明

- 1.1 网页漏洞利用告警
  - 1.1.1 字段说明
  - 1.1.2 字典类型字段说明
  - 1.1.3 范例
- 1.2 Webshell上传告警
  - 1.2.1 字段说明
  - 1.2.2 字典类型字段说明
  - 1.2.3 范例
- 1.3 网络攻击告警
  - 1.3.1 字段说明
  - 1.3.2 字典类型字段说明
  - 1.3.3 范例
- 1.4 威胁情报告警
  - 1.4.1 字段说明
  - 1.4.2 字典类型字段说明
  - 1.4.3 范例
- 1.5 系统日志
  - 1.5.1 字段说明
  - 1.5.2 字典类型字段说明
  - 1.5.3 范例
- 1.6 操作审计
  - 1.6.1 字段说明
  - 1.6.2 字典类型字段说明

---

## 1.1 网页漏洞利用告警

### 1.1.1 字段说明

| 字段名 | 字段含义 |
|---|---|
| alert_type | 告警类型 |
| serialno | 设备序列号 |
| rule_id | 规则ID |
| rule_name | 规则名称 |
| write_date | 告警时间 |
| vuln_type | 漏洞类型 |
| sip | 源IP |
| sport | 源端口 |
| dip | 目的IP |
| dport | 目的端口 |
| severity | 威胁等级 |
| host | 主机地址 |
| parameter | 参数 |
| uri | URI |
| filename | 文件名 |
| referer | referer |
| method | 请求方法 |
| vuln_desc | 漏洞描述 |
| public_date | 公布时间 |
| vuln_harm | 漏洞危害 |
| solution | 解决方案 |
| confidence | 确信度 |
| victim_type | 受害主机类型 |
| attack_flag | 攻击标识 |
| attacker | 攻击者 |
| victim | 受攻击者 |
| attack_result | 攻击结果 |
| kill_chain | 攻击链 |
| code_language | 建站程序 |
| public_date | 漏洞发布时间 |
| rule_version | 规则版本 |
| xff | X-Forwarded-For字段 |
| vlan_id | VLAN字段 |
| vxlan_id | VXLAN字段 |

### 1.1.2 字典类型字段说明

**Severity威胁等级：**

- 2：低危
- 4：中危
- 6：高危
- 8：危急

**Attack_result 攻击结果：**

- 0：企图
- 1：成功
- 2：失陷
- 3：失败

### 1.1.3 范例

```
webids_alert|!V3ee8315f|!26843s612|!dedecms XSS|!1521071081|!跨站脚本攻击（XSS）|!192.168.42.41|!62594|!192.168.138.180|!80|!6|! aiweiyang.w164.mc-test.com|!adminDirHand="/"></script><script>alert(1);</script>|!/include/dialog/config.php?adminDirHand="/"></script><script>alert(1);</script>|!Y29uZmlnLnBocA==|! http://aiweiyang.w164.mc-test.com/include/dialog/config.php?adminDirHand="/"></script><script>alert(1);</script>|!GET|!dedecmsXSS|!2014-02-26 00:00:00|!dedecmsXSS|!请升级至官方最新版本或下载最新补丁|!80|!server|!true|!192.168.42.41|!192.168.138.180|!1|!0x02020000|!PHP|!2014-02-26 00:00:00|!1|!4.6.7.8|!!0
```

---

## 1.2 webshell上传告警

### 1.2.1 字段说明

| 字段名 | 字段含义 |
|---|---|
| alert_type | 告警类型 |
| serialno | 设备序列号 |
| rule_id | 规则ID |
| host | 主机地址 |
| uri | URI |
| file_md5 | 文件MD5 |
| sip | 源IP |
| sport | 源端口 |
| dip | 目的IP |
| dport | 目的端口 |
| attack_type | 攻击类型 |
| write_date | 告警时间 |
| severity | 威胁等级 |
| attack_desc | 攻击描述 |
| attack_harm | 攻击危害 |
| confidence | 确信度 |
| file_dir | 文件方向 |
| victim_type | 受害主机类型 |
| attack_flag | 攻击标识 |
| attacker | 攻击者 |
| victim | 受攻击者 |
| attack_result | 攻击结果 |
| kill_chain | 攻击链 |
| rule_name | 规则名称 |
| vlan_id | VLAN字段 |
| vxlan_id | VXLAN字段 |

### 1.2.2 字典类型字段说明

**Severity威胁等级：**

- 2：低危
- 5：中危
- 8：危急

**Attack_result 攻击结果：**

- 0：企图
- 1：成功
- 2：失陷
- 3：失败

### 1.2.3 范例

```
webshell_alert|!V3ee8315f|!10000|!10.16.66.68|!/dvwa/vulnerabilities/upload/|!34d83a44ea9f21d4d7d23fb66734e5ef|!10.18.219.28|!62776|!10.16.66.68|!80|!中国菜刀变形|!1521017081|!8|!攻击者企图上传一个后门文件。后门程序一般是指那些绕过安全性控制而获取对程序或系统访问权的程序。该后门文件通过调用PHP函数eval来直接执行客户传入的数据（一般是一段代码），实现对服务器的操作和控制。若服务器被此菜刀程序后可能导致以下后果：1.整个网站或服务器被黑客控制，变成傀儡机；2.核心数据被破坏，造成用户信息泄露。|!建议阻断该连接，排查是否数据库存在口令，或者存在其他漏洞或后门。|!upload|!server|!true|!10.18.219.28|!10.16.66.68|!0|!0x02010000|!中国菜刀变形.A|!!0
```

---

## 1.3 网络攻击告警

### 1.3.1 字段说明

| 字段名 | 字段含义 |
|---|---|
| alert_type | 告警类型 |
| serialno | 设备序列号 |
| rule_id | 规则ID |
| rule_name | 规则名称 |
| write_date | 告警时间 |
| vuln_type | 漏洞类型 |
| sip | 源IP |
| sport | 源端口 |
| dip | 目的IP |
| dport | 目的端口 |
| severity | 威胁等级 |
| info_id | 公开漏洞编号 |
| affected_system | 受影响系统 |
| protocol_id | 协议ID |
| attack_method | 攻击方法 |
| appid | 应用ID |
| detail_info | 漏洞详情信息 |
| bulletin | 公告 |
| confidence | 确信度 |
| victim_type | 受害主机类型 |
| attack_flag | 攻击标识 |
| attacker | 攻击者 |
| victim | 受攻击者 |
| cnnvd | CNNVD编号 |
| attack_result | 攻击结果 |
| kill_chain | 攻击链 |
| rule_version | 规则版本 |
| vlan_id | VLAN字段 |
| vxlan_id | VXLAN字段 |

### 1.3.2 字典类型字段说明

**Severity威胁等级：**

- 2：低危
- 4：中危
- 6：高危
- 8：危急

**Appid应用ID：**

| 编号 | 应用 | 编号 | 应用 | 编号 | 应用 |
|---|---|---|---|---|---|
| 1 | finger | 45 | ftp-data | 89 | icmp |
| 2 | netop-remote-control | 46 | ftp | 90 | modbus |
| 3 | netbios-ss | 47 | google-base | 91 | ip-messenger |
| 4 | smtp | 48 | pcanywhere | 92 | tales-runner |
| 5 | ctd-dummy | 49 | radius | 93 | hp-data-protector |
| 6 | yy-voice | 50 | dhcp | 94 | tcp |
| 7 | h245 | 51 | tv4play | 95 | maplestory |
| 8 | ipsec-esp-udp | 52 | corba | 96 | generic |
| 9 | freegate | 53 | sccp | 97 | mssql-db |
| 10 | stun | 54 | maxdb | 98 | postgres |
| 11 | spotify | 55 | dccp | 99 | ipv6-icmp |
| 12 | nfs | 56 | unistim | 100 | net2phone |
| 13 | msn-http-gate | 57 | ipv6 | 101 | dnp3 |
| 14 | pptp | 58 | yahoo-im | 102 | ike |
| 15 | gtp | 59 | ezpeer | 103 | sip |
| 16 | gtalk-voice | 60 | playstation-network | 104 | nntp |
| 17 | msn-video | 61 | jabber | 105 | gdbremote |
| 18 | msn-voice | 62 | open-vpn | 106 | irc |
| 19 | ssl | 63 | qq | 107 | gnutella-internal |
| 20 | msn | 64 | telnet | 108 | kerberos |
| 21 | db2 | 65 | rediffbol | 109 | simplify |
| 22 | yoics | 66 | cpq-wbem | 110 | ntp |
| 23 | imvu | 67 | xdmcp | 111 | rpc |
| 24 | asterisk-iax | 68 | gtalk-p2p | 112 | viber |
| 25 | mgcp | 69 | gds-db | 113 | gtalk-file-transfer |
| 26 | vmware | 70 | pop3 | 114 | google-talk |
| 27 | llmnr | 71 | rtmp | 115 | iccp |
| 28 | netbios-dg | 72 | ldap | 116 | tivoli-storage-manager |
| 29 | h225 | 73 | tcp | 117 | ali-wangwang |
| 30 | mssql-mon | 74 | xbox-live | 118 | xware-xtrm |
| 31 | h248 | 75 | pgm | 119 | socks |
| 32 | nintendo-wfc | 76 | teamviewer | 120 | sybase |
| 33 | msn-file-transfer | 77 | http | 121 | mongodb |
| 34 | buddybuddy | 78 | sctp | 122 | vnc |
| 35 | imap | 79 | gnutella | 123 | netbios-ns |
| 36 | t3 | 80 | mail_ru-agent | 124 | time |
| 37 | wins | 81 | aim-file-transfer | 125 | lwapp |
| 38 | fetion | 82 | igmp | 126 | informix |
| 39 | snpp | 83 | oracle | 127 | softros-messenger |
| 40 | ms-virtualserver | 84 | bomgar | 128 | nateon-internal |
| 41 | t_120 | 85 | subspace | 129 | oracle-bi |
| 42 | teredo | 86 | mms | 130 | dns |
| 43 | cvs | 87 | pre-app | 131 | citrix-jedi |
| 44 | bittorrent | 88 | msrpc | 132 | aol-proxy |
| 133 | bit-internal | 143 | snmp | 153 | ameba-now-posting |
| 134 | rmcp | 144 | mysql | 154 | facebook-posting |
| 135 | share-p2p | 145 | cotp | 155 | linkedin-posting |
| 136 | gotomypc | 146 | ssh | 156 | pastebin-posting |
| 137 | bit-predict | 147 | tftp | 157 | pinterest-posting |
| 138 | lpd | 148 | icq | 158 | qik-posting |
| 139 | unknown | 149 | rtsp | 159 | sharepoint-blog-posting |
| 140 | smb | 150 | panav | 160 | storify-posting |
| 141 | showmypc | 151 | skype-probe | 161 | tumblr-posting |
| 142 | adnstream | 152 | ameba-blog-posting | 200 | http_lite |
| 201 | file-parser | 203 | smb-8-1 | 205 | damengdb |
| 202 | brass | 204 | bacnet | | |

**Attack_result 攻击结果：**

- 0：企图
- 1：成功
- 2：失陷
- 3：失败

### 1.3.3 范例

```
ips_alert|!V3ee8315f|!23075|!数据库敏感操作执行成功|!1639382450|!其他|!13.192.242.56|!43234|!74.97.188.39|!3306|!8|!|!6|!远程|!144|!发现数据库有敏感操作，包括文件读写和创建自定义函数，以及执行系统命令等。其中：#015#012MySQL常见敏感操作函数或命令有dumpfile()、outfile()和create function；#015#012SQL Server 常见敏感操作函数或命令有xp_cmdshell、xp_regwrite、xp_create_subdir、backup database、exec xp_fixeddrives、xp_dir、xp_dirtree、xp_makecab；#015#012Oracle 常见敏感操作函数或命令有dbms_snap_internal.DELETE_REFRESH_OPERATIONS、dbms_output.put_line(SYS.OLAPIMPL_T.ODCITABLESTART等。|!建议阻断该连接，排查是否数据库存在弱口令，或者存在其他漏洞或后门。|!80|!server|!true|!13.192.242.56|!74.97.188.39|!!!1|!0x02050100|!1.0|!!!0
```

---

## 1.4 威胁情报告警

### 1.4.1 字段说明

| 字段名 | 字段含义 |
|---|---|
| alert_type | 告警类型 |
| serialno | 设备序列号 |
| rule_id | 情报ID |
| host | 主机地址 |
| uri | URI |
| file_md5 | 传输文件MD5 |
| sip | 源IP |
| sport | 源端口 |
| dip | 目的IP |
| dport | 目的端口 |
| write_date | 告警时间 |
| severity | 威胁等级 |
| confidence | 确信度 |
| file_dir | 文件方向 |
| attacker | 攻击者 |
| victim | 受攻击者 |
| attack_type | 威胁类型 |
| attack_name | 威胁名称 |
| IOC | 威胁情报 |
| IOC_type | 威胁情报类型 |
| proto | 应用层协议 |
| tproto | 传输层协议 |
| dns_type | DNS请求响应类型 |
| dnsarecord | DNS A记录 |
| file_name | 传输文件名 |
| malicious_family | 恶意家族 |
| campaign | 攻击事件/团伙 |
| targeted | 定向攻击 |
| platform | 影响平台 |
| ioc_source | 情报来源 |
| vlan_id | VLAN字段 |
| vxlan_id | VXLAN字段 |

### 1.4.2 字典类型字段说明

**Severity威胁等级：**

- 3：低危
- 5：中危
- 7：高危
- 9：危急

**Ioc_source 情报来源：**

- 0：云端下发
- 1：自定义

### 1.4.3 范例

```
ioc_alert|!V3ee8315f|!5782621921543776263|!natco1.no-ip.net|!!|!|!192.168.45.129|!65272|!192.168.45.2|!53|!1521034302000|!7|!high|!0|!58.158.177.102|!192.168.45.129|!远控木马！Gaza Cybergang APT组织活动事件!|natco1.no-ip.net|host|!dns|!udp|!1|!58.158.177.102|!!!Delf|!Gaza Cybergang|!0|!Windows|!0|!!0
```

---

## 1.5 系统日志

### 1.5.1 字段说明

| 字段名 | 字段含义 |
|---|---|
| updatetime | 更新时间 |
| level | 日志级别 |
| serialno | 设备序列号 |
| sub_type | 日志子类型 |
| note | 日志详情 |
| type | 日志类型 |
| log_type | 日志父类型 |

### 1.5.2 字典类型字段说明

**Sub_type日志子类型：**

- 0：运行日志
- 1：升级日志

**Type日志类型：**

- 2：CPU过高
- 3：内存过高
- 4：硬盘故障
- 5：证书过期
- 11：磁盘占用
- 14：异常日志

**Level日志级别：**

- 3：错误
- 4：警告
- 5：通知

### 1.5.3 范例

```
updatetime:2022-12-29 15:44:28.224151|!level:3|!serialno:214585853|!sub_type:0|!note:【syslog服务器-1.1.1.1:514】连接断开|!type:14|!log_type:系统日志
```

---

## 1.6 操作审计

### 1.6.1 字段说明

| 字段名 | 字段含义 |
|---|---|
| username | 操作者 |
| serialno | 设备序列号 |
| submod | 二级模块 |
| detail | 日志详情 |
| updatetime | 更新时间 |
| ip | 设备IP |
| sub2 | 三级模块 |
| log_type | 日志父类型 |
| module | 一级模块 |
| sub_type | 日志子类型 |

### 1.6.2 字典类型字段说明

**Sub_type日志子类型：**

- 0：新增
- 1：删除
- 2：编辑
- 3：查看

### 1.6.3 范例

```
username:admin|!serialno:214585853|!submod:安全性配置|!detail:message：获取敏感密码成功|!updatetime:2022-12-29 15:44:14.861246|!ip:10.91.130.33|!sub2:敏感操作密码|!log_type:操作审计|!module:系统管理|!sub_type:3
```
