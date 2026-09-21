import { useEffect, useState } from 'react';
import { Card, Button, Input, InputNumber, Select, Table, Tabs, Typography, Space, Tag, App, Modal } from 'antd';
import { ArrowLeftOutlined, PlusOutlined } from '@ant-design/icons';
import { configApi } from '../api/config';
import { errMsg } from '../api/http';
import type {
  FreqConfig, GatingConfig, ModelConfig, DetectionConfig, IngestConfig,
  SourcesConfig, WebhookConfig, SourceStatus, ParsersConfig, ParserRule, AssetItem,
} from '../types/models';

interface PresetVals { suppress_below: number; escalate_above: number; budget: number; }

const ALL_FIELDS = ['correlation_uid', 'title', 'strength', 'status', 'verdict', 'entities', 'ips', 'alerts',
  'report.verdict', 'report.confidence', 'report.digest', 'report.attack_chain', 'report.iocs', 'report.remediations', 'report.unknowns'];

const FIELD_GROUPS: [string, [string, string][]][] = [
  ['案件身份', [['correlation_uid', 'ID'], ['title', '标题'], ['strength', '强度'], ['status', '状态'], ['verdict', '定性']]],
  ['关联', [['entities', '实体'], ['ips', 'IP'], ['alerts', '告警']]],
  ['报告', [['report.verdict', '定性'], ['report.confidence', '置信度'], ['report.digest', '摘要'],
    ['report.attack_chain', '攻击链'], ['report.iocs', 'IOC'], ['report.remediations', '处置建议'], ['report.unknowns', '待查']]],
];

const SOURCE_SECTIONS = ['facility', 'hostname', 'tag', 'ip'] as const;

function KeyValueMap({ entries, onChange, keyPh, valPh }: {
  entries: [string, string][];
  onChange: (e: [string, string][]) => void;
  keyPh: string;
  valPh: string;
}) {
  return (
    <div>
      {entries.map(([k, v], i) => (
        <Space key={i} style={{ display: 'flex', marginBottom: 8 }}>
          <Input value={k} placeholder={keyPh} onChange={(e) => { const n = [...entries]; n[i] = [e.target.value, v]; onChange(n); }} />
          <Typography.Text type="secondary">→</Typography.Text>
          <Input value={v} placeholder={valPh} onChange={(e) => { const n = [...entries]; n[i] = [k, e.target.value]; onChange(n); }} />
          <Button onClick={() => onChange(entries.filter((_, j) => j !== i))}>删</Button>
        </Space>
      ))}
      <Button icon={<PlusOutlined />} onClick={() => onChange([...entries, ['', '']])}>添加</Button>
    </div>
  );
}

export default function AdvancedSettings({ onBack }: { onBack: () => void }) {
  const { message, modal } = App.useApp();
  const [presets, setPresets] = useState<Record<string, PresetVals> | null>(null);
  const [edits, setEdits] = useState<Record<string, PresetVals>>({});
  const [freq, setFreq] = useState<FreqConfig | null>(null);
  const [gating, setGating] = useState<GatingConfig | null>(null);
  const [model, setModel] = useState<ModelConfig | null>(null);
  const [testingModel, setTestingModel] = useState<'system1' | 'system2' | null>(null);
  const [detection, setDetection] = useState<DetectionConfig | null>(null);
  const [ingest, setIngest] = useState<IngestConfig | null>(null);
  const [sources, setSources] = useState<SourcesConfig | null>(null);
  const [sourceStatus, setSourceStatus] = useState<SourceStatus[] | null>(null);
  const [parsers, setParsers] = useState<ParsersConfig | null>(null);
  const [parserSource, setParserSource] = useState('');
  const [parserSamples, setParserSamples] = useState('');
  const [parserPreview, setParserPreview] = useState('');
  const [parserGenerating, setParserGenerating] = useState(false);
  const [ruleDetail, setRuleDetail] = useState<{ source: string; index: number; isNew: boolean } | null>(null);
  const [ruleDraft, setRuleDraft] = useState('');
  const [webhooks, setWebhooks] = useState<WebhookConfig[] | null>(null);
  const [memory, setMemory] = useState<any[] | null>(null);
  const [feedback, setFeedback] = useState<any[] | null>(null);
  const [whName, setWhName] = useState('');
  const [whUrl, setWhUrl] = useState('');
  const [whTrigger, setWhTrigger] = useState('escalated');
  const [whFields, setWhFields] = useState<string[]>(ALL_FIELDS);
  const [whToken, setWhToken] = useState('');
  const [whHeaders, setWhHeaders] = useState<[string, string][]>([]);
  const [whBody, setWhBody] = useState('');
  const [assets, setAssets] = useState<AssetItem[]>([]);
  const [batchOpen, setBatchOpen] = useState(false);
  const [batchText, setBatchText] = useState('');

  const load = async () => {
    try {
      const [p, f, g, m, d, ig, so, ss, pa, wh, mem, fb, as] = await Promise.all([
        configApi.presets(), configApi.freq(), configApi.gating(), configApi.model(),
        configApi.detection(), configApi.ingest(), configApi.sources(), configApi.sourceStatus(),
        configApi.parsers(), configApi.webhooks(), configApi.memory(), configApi.feedback(),
        configApi.assets(),
      ]);
      setPresets(p); setFreq(f); setGating(g); setModel(m); setDetection(d); setIngest(ig);
      setSources(so); setSourceStatus(ss.items); setParsers(pa); setWebhooks(wh.items);
      setMemory(mem.items); setFeedback(fb.items); setAssets(as.items);
    } catch (e) {
      message.error(errMsg(e));
    }
  };
  useEffect(() => { load(); }, []);

  const save = async (fn: () => Promise<void>, ok: string) => {
    try {
      await fn();
      message.success(ok);
      load();
    } catch (e) {
      message.error(errMsg(e));
    }
  };

  const testModel = async (target: 'system1' | 'system2') => {
    if (!model) return;
    setTestingModel(target);
    try {
      const r = await configApi.testModel({ ...model, target });
      const label = target === 'system1' ? '系统1' : '系统2';
      if (r.ok) message.success(`${label} 连接正常（${r.elapsed}s）`);
      else message.error(`${label} 测试失败：${r.error}`);
    } catch (e) {
      message.error(errMsg(e));
    } finally {
      setTestingModel(null);
    }
  };

  const updateAsset = (i: number, k: keyof AssetItem, v: string) =>
    setAssets((s) => s.map((a, j) => (j === i ? { ...a, [k]: v } : a)));
  const addAsset = () => setAssets((s) => [...s, { role: '', value: '', criticality: 'normal' }]);
  const removeAsset = (i: number) => setAssets((s) => s.filter((_, j) => j !== i));
  const saveAssets = () =>
    save(async () => {
      const cleaned = assets.filter((a) => a.role.trim() && a.value.trim());
      setAssets((await configApi.setAssets(cleaned)).items);
    }, '已保存资产清单');
  const doBatchImport = () => {
    const parsed = batchText.split('\n').map((l) => l.trim()).filter(Boolean).map((l) => {
      const parts = l.split(/\s+/);
      return { role: parts[1] || '内网网段', value: parts[0], criticality: 'normal' };
    });
    setAssets((s) => [...s, ...parsed]);
    setBatchOpen(false);
    setBatchText('');
  };

  const ruleSummary = (rule: ParserRule): string => {
    const m = rule.map || {};
    const ent = m.entities?.length || 0;
    const sep = rule.type === 'dissect'
      ? `分隔「${rule.delimiter}」· ${rule.fields?.length || 0} 字段`
      : `「${rule.field_split}」/「${rule.value_split}」`;
    return `${sep} · asset=${m.asset || '-'} · ${ent} 实体`;
  };

  // 来源的风险字段缺失提醒：map 未配 severity / attack_result 时标黄
  const missingRiskFields = (src: string): string[] => {
    const cfg = parsers?.[src];
    const maps = (cfg?.parsers ?? []).map((r) => r.map || {});
    const miss: string[] = [];
    if (!maps.some((m) => m.severity)) miss.push('缺威胁等级');
    if (!maps.some((m) => m.attack_result)) miss.push('缺攻击结果');
    return miss;
  };

  const toggleRule = async (source: string, index: number) => {
    if (!parsers) return;
    const srcCfg = parsers[source];
    const list = [...(srcCfg.parsers || [])];
    const wasDisabled = list[index].enabled === false;
    list[index] = { ...list[index], enabled: wasDisabled };
    await save(
      async () => { setParsers(await configApi.setParsers({ ...parsers, [source]: { ...srcCfg, parsers: list } })); },
      wasDisabled ? '已启用规则' : '已停用规则',
    );
  };

  const deleteRule = async (source: string, index: number) => {
    if (!parsers) return;
    modal.confirm({
      title: '删除该条规则？',
      onOk: async () => {
        const srcCfg = parsers[source];
        const list = (srcCfg?.parsers || []).filter((_, i) => i !== index);
        let next: ParsersConfig;
        if (list.length === 0) { next = { ...parsers }; delete next[source]; }
        else next = { ...parsers, [source]: { ...srcCfg, parsers: list } };
        await save(async () => { setParsers(await configApi.setParsers(next)); }, '已删除规则');
      },
    });
  };

  const saveRuleDetail = async () => {
    if (!ruleDetail || !parsers) return;
    let rule: ParserRule;
    try { rule = JSON.parse(ruleDraft); } catch { message.error('规则 JSON 不合法'); return; }
    const srcCfg = parsers[ruleDetail.source] || { parsers: [] };
    const list = [...(srcCfg.parsers || [])];
    list[ruleDetail.index] = rule;
    await save(
      async () => { setParsers(await configApi.setParsers({ ...parsers, [ruleDetail.source]: { ...srcCfg, parsers: list } })); },
      '已保存规则',
    );
    setRuleDetail(null);
  };

  const assetsTab = (
    <Card size="small" title="资产清单">
      <Typography.Paragraph type="secondary">
        配置「我们自己的资产」：角色 + IP/CIDR/域名 + 敏感度。命中资产的 IP/域名会在研判时标注；源 IP 为「出口IP」时温和降噪（置信度 ×0.85）。
      </Typography.Paragraph>
      <Table<AssetItem>
        rowKey={(_, i) => String(i)}
        dataSource={assets}
        pagination={false}
        size="small"
        columns={[
          {
            title: '角色',
            dataIndex: 'role',
            width: 200,
            render: (v: string, _: AssetItem, i: number) => (
              <Input value={v} size="small" placeholder="出口IP / 内网网段 / 生产网段" onChange={(e) => updateAsset(i, 'role', e.target.value)} />
            ),
          },
          {
            title: '值（IP / CIDR / 域名）',
            dataIndex: 'value',
            render: (v: string, _: AssetItem, i: number) => (
              <Input value={v} size="small" placeholder="1.2.3.4 / 10.0.0.0/8 / corp.example.com" onChange={(e) => updateAsset(i, 'value', e.target.value)} />
            ),
          },
          {
            title: '敏感度',
            dataIndex: 'criticality',
            width: 120,
            render: (v: string, _: AssetItem, i: number) => (
              <Select
                value={v || 'normal'} size="small" style={{ width: '100%' }}
                onChange={(nv) => updateAsset(i, 'criticality', nv)}
                options={[
                  { value: 'normal', label: '普通' },
                  { value: 'important', label: '重要' },
                  { value: 'critical', label: '核心' },
                ]}
              />
            ),
          },
          {
            title: '',
            width: 56,
            render: (_: unknown, __: AssetItem, i: number) => (
              <Button size="small" danger onClick={() => removeAsset(i)}>删</Button>
            ),
          },
        ]}
      />
      <Space style={{ marginTop: 12 }}>
        <Button icon={<PlusOutlined />} onClick={addAsset}>添加资产</Button>
        <Button onClick={() => setBatchOpen(true)}>批量导入</Button>
        <Button type="primary" onClick={saveAssets}>保存</Button>
      </Space>
      <Modal title="批量导入资产" open={batchOpen} onCancel={() => setBatchOpen(false)} onOk={doBatchImport} okText="导入">
        <Typography.Paragraph type="secondary">
          每行一条：`IP/CIDR/域名 角色`（角色可省略，默认「内网网段」）。
        </Typography.Paragraph>
        <Input.TextArea
          rows={6} placeholder={'1.2.3.4 出口IP\n10.0.0.0/8 内网网段\ncorp.example.com 自有域名'}
          value={batchText} onChange={(e) => setBatchText(e.target.value)}
        />
      </Modal>
    </Card>
  );

  const presetsTab = (
    <Card size="small" title="阈值配置（四档）">
      <Typography.Paragraph type="secondary">改这里即可，不用碰代码；改动立即影响入库和流式处理。</Typography.Paragraph>
      <Table
        rowKey="name" size="small" pagination={false}
        dataSource={presets ? Object.entries(presets).map(([name, p]) => ({ name, ...(edits[name] || p) })) : []}
        columns={[
          { title: '档位', dataIndex: 'name', render: (v: string) => <b>{v}</b> },
          {
            title: '抑制线', dataIndex: 'suppress_below',
            render: (_: number, r: any) => (
              <InputNumber size="small" step={0.05} value={r.suppress_below} onChange={(v) => setEdits((s) => ({ ...s, [r.name]: { ...(s[r.name] || presets![r.name]), suppress_below: v ?? 0 } }))} />
            ),
          },
          {
            title: '顶出线', dataIndex: 'escalate_above',
            render: (_: number, r: any) => (
              <InputNumber size="small" step={0.05} value={r.escalate_above} onChange={(v) => setEdits((s) => ({ ...s, [r.name]: { ...(s[r.name] || presets![r.name]), escalate_above: v ?? 0 } }))} />
            ),
          },
          {
            title: '预算', dataIndex: 'budget',
            render: (_: number, r: any) => (
              <InputNumber size="small" value={r.budget} onChange={(v) => setEdits((s) => ({ ...s, [r.name]: { ...(s[r.name] || presets![r.name]), budget: v ?? 0 } }))} />
            ),
          },
          {
            title: '', key: 'op',
            render: (_: unknown, r: any) => <Button size="small" onClick={() => save(async () => { await configApi.updatePreset(r.name, edits[r.name]); }, `已保存「${r.name}」档`)}>保存</Button>,
          },
        ]}
      />
    </Card>
  );

  const modelTab = (
    <Card size="small" title="模型接入">
      <Typography.Paragraph type="secondary">key 留空 = 回退 .env；key 掩码显示，输入新值才会覆盖。</Typography.Paragraph>
      {model && (
        <Space orientation="vertical" size={12} style={{ width: '100%' }}>
          <div>
            <Typography.Text strong>杏仁核（系统1）</Typography.Text>
            <Space wrap style={{ display: 'flex', marginTop: 8 }}>
              <Input addonBefore="API key" placeholder="••••（未改则不覆盖）" value={model.api_key} onChange={(e) => setModel({ ...model, api_key: e.target.value })} />
              <Input addonBefore="base URL" value={model.base_url} onChange={(e) => setModel({ ...model, base_url: e.target.value })} />
              <Input addonBefore="模型名" value={model.model} onChange={(e) => setModel({ ...model, model: e.target.value })} />
              <Button loading={testingModel === 'system1'} onClick={() => testModel('system1')}>测试</Button>
            </Space>
          </div>
          <div>
            <Typography.Text strong>前额叶（系统2 深想）</Typography.Text>
            <Space wrap style={{ display: 'flex', marginTop: 8 }}>
              <Input addonBefore="API key" placeholder="••••（未改则不覆盖）" value={model.deep_api_key} onChange={(e) => setModel({ ...model, deep_api_key: e.target.value })} />
              <Input addonBefore="base URL" placeholder="空 = 回退杏仁核" value={model.deep_base_url} onChange={(e) => setModel({ ...model, deep_base_url: e.target.value })} />
              <Input addonBefore="模型名" value={model.deep_model} onChange={(e) => setModel({ ...model, deep_model: e.target.value })} />
              <Button loading={testingModel === 'system2'} onClick={() => testModel('system2')}>测试</Button>
            </Space>
          </div>
          <Space wrap>
            <InputNumber addonBefore="temperature" step={0.1} value={model.temperature} onChange={(v) => setModel({ ...model, temperature: v ?? 0 })} />
            <InputNumber addonBefore="超时（秒）" value={model.timeout} onChange={(v) => setModel({ ...model, timeout: v ?? 120 })} />
            <Button type="primary" onClick={() => save(async () => { setModel(await configApi.setModel(model)); }, '已保存模型接入')}>保存</Button>
          </Space>
        </Space>
      )}
    </Card>
  );

  const freqTab = (
    <Card size="small" title="频率降级">
      <Typography.Paragraph type="secondary">时间窗外历史同类型告警极多 → 判为业务误报并降级置信度（防刷屏误报）。</Typography.Paragraph>
      {freq && (
        <Space wrap>
          <InputNumber addonBefore="时间窗（秒）" value={freq.window} onChange={(v) => setFreq({ ...freq, window: v ?? 0 })} />
          <InputNumber addonBefore="频次阈值（次）" value={freq.threshold} onChange={(v) => setFreq({ ...freq, threshold: v ?? 0 })} />
          <InputNumber addonBefore="置信度折扣（0~1）" step={0.05} value={freq.demote} onChange={(v) => setFreq({ ...freq, demote: v ?? 0 })} />
          <Button type="primary" onClick={() => save(async () => { setFreq(await configApi.setFreq(freq)); }, '已保存频率降级')}>保存</Button>
        </Space>
      )}
    </Card>
  );

  const gatingTab = (
    <Card size="small" title="前额叶 唤醒门槛">
      <Typography.Paragraph type="secondary">单信号案件默认不唤醒前额叶（除非置信度 ≥ 地板值）；预算窗口内最多唤醒「预算」个不同案件。</Typography.Paragraph>
      {gating && (
        <Space wrap>
          <InputNumber addonBefore="单信号地板值（0~1）" step={0.01} value={gating.single_signal_floor} onChange={(v) => setGating({ ...gating, single_signal_floor: v ?? 0 })} />
          <InputNumber addonBefore="预算窗口（秒）" value={gating.budget_window} onChange={(v) => setGating({ ...gating, budget_window: v ?? 0 })} />
          <Button type="primary" onClick={() => save(async () => { setGating(await configApi.setGating(gating)); }, '已保存前额叶 唤醒门槛')}>保存</Button>
        </Space>
      )}
    </Card>
  );

  const detectionTab = (
    <Card size="small" title="检测调参">
      <Typography.Paragraph type="secondary">案件强度 = 最强信号置信度 + min(封顶, 每额外告警 × 链加成)。</Typography.Paragraph>
      {detection && (
        <Space orientation="vertical" size={12} style={{ width: '100%' }}>
          <Space wrap>
            <InputNumber addonBefore="链加成" step={0.05} value={detection.chain_bonus} onChange={(v) => setDetection({ ...detection, chain_bonus: v ?? 0 })} />
            <InputNumber addonBefore="封顶" step={0.05} value={detection.chain_cap} onChange={(v) => setDetection({ ...detection, chain_cap: v ?? 0 })} />
            <InputNumber addonBefore="重分析阈值（条）" value={detection.grew} onChange={(v) => setDetection({ ...detection, grew: v ?? 0 })} />
            <InputNumber addonBefore="RAG 条数" value={detection.rag_limit} onChange={(v) => setDetection({ ...detection, rag_limit: v ?? 0 })} />
            <InputNumber addonBefore="固有免疫 conf" step={0.05} value={detection.innate_conf} onChange={(v) => setDetection({ ...detection, innate_conf: v ?? 0 })} />
            <InputNumber addonBefore="放回 conf" step={0.05} value={detection.restore_conf} onChange={(v) => setDetection({ ...detection, restore_conf: v ?? 0 })} />
            <InputNumber addonBefore="白名单 TTL（天）" value={detection.tolerance_ttl_days} onChange={(v) => setDetection({ ...detection, tolerance_ttl_days: v ?? 0 })} />
          </Space>
          <div>
            <Typography.Text strong>Mock 规则（仅 mock 模式生效）</Typography.Text>
            {detection.mock_indicators.map(([kw, w], i) => (
              <Space key={i} style={{ display: 'flex', margin: '8px 0' }}>
                <Input placeholder="关键词" value={kw} onChange={(e) => { const arr = [...detection.mock_indicators]; arr[i] = [e.target.value, w]; setDetection({ ...detection, mock_indicators: arr }); }} />
                <InputNumber step={0.01} value={w} onChange={(v) => { const arr = [...detection.mock_indicators]; arr[i] = [kw, v ?? 0]; setDetection({ ...detection, mock_indicators: arr }); }} style={{ width: 100 }} />
                <Button onClick={() => setDetection({ ...detection, mock_indicators: detection.mock_indicators.filter((_, j) => j !== i) })}>删</Button>
              </Space>
            ))}
            <Button icon={<PlusOutlined />} onClick={() => setDetection({ ...detection, mock_indicators: [...detection.mock_indicators, ['', 0.1]] })}>添加关键词</Button>
          </div>
          <Space wrap>
            <InputNumber addonBefore="base" step={0.01} value={detection.mock_base} onChange={(v) => setDetection({ ...detection, mock_base: v ?? 0 })} />
            <InputNumber addonBefore="ceiling" step={0.01} value={detection.mock_ceiling} onChange={(v) => setDetection({ ...detection, mock_ceiling: v ?? 0 })} />
            <InputNumber addonBefore="cutoff" step={0.01} value={detection.mock_cutoff} onChange={(v) => setDetection({ ...detection, mock_cutoff: v ?? 0 })} />
            <InputNumber addonBefore="no_hit" step={0.01} value={detection.mock_no_hit} onChange={(v) => setDetection({ ...detection, mock_no_hit: v ?? 0 })} />
          </Space>
          <Button type="primary" onClick={() => save(async () => { setDetection(await configApi.setDetection(detection)); }, '已保存检测调参')}>保存</Button>
        </Space>
      )}
    </Card>
  );

  const ingestTab = (
    <Card size="small" title="数据接入（syslog）">
      {ingest && (
        <Space orientation="vertical" size={12} style={{ width: '100%' }}>
          <Space wrap>
            <Input addonBefore="syslog 地址" value={ingest.syslog_bind} onChange={(e) => setIngest({ ...ingest, syslog_bind: e.target.value })} />
            <InputNumber addonBefore="syslog 端口" value={ingest.syslog_port} onChange={(v) => setIngest({ ...ingest, syslog_port: v ?? 0 })} />
            <InputNumber addonBefore="巩固间隔（秒）" value={ingest.consolidate_interval} onChange={(v) => setIngest({ ...ingest, consolidate_interval: v ?? 0 })} />
            <InputNumber addonBefore="告警保留（天）" value={ingest.retention_alert_days} onChange={(v) => setIngest({ ...ingest, retention_alert_days: v ?? 0 })} />
            <InputNumber addonBefore="案件保留（天）" value={ingest.retention_case_days} onChange={(v) => setIngest({ ...ingest, retention_case_days: v ?? 0 })} />
            <Input addonBefore="API token" placeholder="••••（空 = 免鉴权）" value={ingest.api_token} onChange={(e) => setIngest({ ...ingest, api_token: e.target.value })} />
          </Space>
          <Button type="primary" onClick={() => save(async () => { setIngest(await configApi.setIngest(ingest)); }, '已保存接入配置')}>保存</Button>
          <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
            syslog 地址/端口改后需重启后端；巩固间隔、保留天数与 API token 下个周期生效。
          </Typography.Paragraph>

          {sourceStatus && sourceStatus.length > 0 && (
            <div>
              <Typography.Text strong>已配置来源</Typography.Text>
              <div style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {sourceStatus.map((s) => (
                  <Tag key={s.source}>
                    {s.source}：{s.count ? `${s.count} 条告警` : '暂无数据'}
                  </Tag>
                ))}
              </div>
            </div>
          )}

          {sources && (
            <div>
              <Typography.Text strong>来源映射（优先级 ip &gt; tag &gt; hostname &gt; facility）</Typography.Text>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginTop: 8 }}>
                {SOURCE_SECTIONS.map((sec) => (
                  <div key={sec}>
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>{sec}</Typography.Text>
                    <KeyValueMap
                      entries={Object.entries(sources[sec])}
                      onChange={(e) => setSources({ ...sources, [sec]: Object.fromEntries(e) })}
                      keyPh={sec === 'ip' ? '1.2.3.4' : sec}
                      valPh="天眼"
                    />
                  </div>
                ))}
              </div>
              <Button type="primary" style={{ marginTop: 8 }} onClick={() => save(async () => {
                const clean: SourcesConfig = { facility: {}, hostname: {}, tag: {}, ip: {} };
                for (const sec of SOURCE_SECTIONS) {
                  for (const [k, v] of Object.entries(sources[sec])) if (k.trim()) clean[sec][k.trim()] = v;
                }
                setSources(await configApi.setSources(clean));
              }, '已保存来源映射')}>保存来源映射</Button>
            </div>
          )}

          <div>
            <Typography.Text strong>来源解析（精确实体）</Typography.Text>
            {parsers && Object.keys(parsers).length > 0 && (
              <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 10 }}>
                {Object.keys(parsers).map((src) => {
                  const cfg = parsers[src];
                  return (
                    <div key={src} style={{ border: '1px solid #e4e7eb', borderRadius: 8, padding: '10px 12px' }}>
                      <Space wrap>
                        <b>{src}</b>
                        {cfg.strip_syslog && <Tag>剥 syslog 头</Tag>}
                        {missingRiskFields(src).map((m) => <Tag color="warning" key={m}>{m}</Tag>)}
                        <Typography.Text type="secondary" style={{ fontSize: 12 }}>{cfg.parsers?.length ?? 0} 条规则</Typography.Text>
                        <Button size="small" onClick={() => { setRuleDetail({ source: src, index: cfg.parsers?.length ?? 0, isNew: true }); setRuleDraft(JSON.stringify({ match: '', type: 'dissect', delimiter: '', fields: [], map: {} }, null, 2)); }}>加规则</Button>
                        <Button size="small" danger onClick={() => save(async () => {
                          const next = { ...(parsers || {}) }; delete next[src]; setParsers(await configApi.setParsers(next));
                        }, '已删除解析配置')}>删来源</Button>
                      </Space>
                      {(cfg.parsers ?? []).map((rule, i) => (
                        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8, paddingTop: 8, borderTop: '1px solid #e4e7eb', opacity: rule.enabled === false ? 0.5 : 1 }}>
                          <Typography.Text code style={{ flex: 1, wordBreak: 'break-all' }}>{rule.match || '(无匹配条件)'}</Typography.Text>
                          <Tag>{rule.type}</Tag>
                          <Typography.Text type="secondary" style={{ fontSize: 12 }}>{ruleSummary(rule)}</Typography.Text>
                          <Button size="small" onClick={() => toggleRule(src, i)}>{rule.enabled === false ? '已停用' : '启用中'}</Button>
                          <Button size="small" onClick={() => { setRuleDetail({ source: src, index: i, isNew: false }); setRuleDraft(JSON.stringify(rule, null, 2)); }}>详情</Button>
                          <Button size="small" danger onClick={() => deleteRule(src, i)}>删</Button>
                        </div>
                      ))}
                    </div>
                  );
                })}
              </div>
            )}
            <Space orientation="vertical" style={{ width: '100%', marginTop: 8 }}>
              <Input addonBefore="来源名" placeholder="天眼" value={parserSource} onChange={(e) => setParserSource(e.target.value)} />
              <Input.TextArea placeholder={'webids_alert|!V3ee8315f|!26843s612|!dedecms XSS|!...'} value={parserSamples} onChange={(e) => setParserSamples(e.target.value)} rows={3} />
              <Button type="primary" loading={parserGenerating} onClick={async () => {
                if (!parserSource.trim() || !parserSamples.trim()) { message.warning('请填来源名和样本'); return; }
                setParserGenerating(true);
                try {
                  const r = await configApi.generateParsers({ source: parserSource.trim(), samples: parserSamples.split('\n').map((l) => l.trim()).filter(Boolean) });
                  setParserPreview(JSON.stringify(r.config, null, 2));
                } catch (e: any) { message.error('生成失败：' + (e?.message || e)); }
                finally { setParserGenerating(false); }
              }}>生成解析配置</Button>
              {parserPreview && (
                <>
                  <Input.TextArea value={parserPreview} onChange={(e) => setParserPreview(e.target.value)} rows={6} style={{ fontFamily: 'monospace' }} />
                  <Button type="primary" onClick={() => save(async () => {
                    let cfg: any;
                    try { cfg = JSON.parse(parserPreview); } catch { message.error('预览不是合法 JSON'); return; }
                    setParsers(await configApi.setParsers({ ...(parsers || {}), [parserSource.trim()]: cfg }));
                  }, '已保存解析配置')}>保存解析配置</Button>
                </>
              )}
            </Space>
          </div>
        </Space>
      )}
    </Card>
  );

  const webhooksTab = (
    <Card size="small" title="案件外发（Webhook）">
      <Typography.Paragraph type="secondary">案件顶出深析后自动 POST 到这些地址，供 SOAR / SIEM / 工单 / 通知等下游消费。</Typography.Paragraph>
      {(webhooks ?? []).map((w, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 0', borderBottom: '1px solid #f0f0f0' }}>
          <div style={{ flex: 1 }}>
            <Typography.Text code style={{ wordBreak: 'break-all' }}>{w.name} → {w.url}</Typography.Text>
            <Tag style={{ marginLeft: 8 }}>{w.trigger === 'escalated' ? '顶出即推' : w.trigger === 'all' ? '全部' : '仅手动'}</Tag>
          </div>
          <Button size="small" onClick={async () => { const r = await configApi.testWebhook(i); message.success(r.ok ? '测试成功' : '测试失败'); }}>测试</Button>
          <Button size="small" danger onClick={() => save(async () => { await configApi.deleteWebhook(i); }, '已删除')}>删</Button>
        </div>
      ))}
      <Space wrap style={{ marginTop: 12 }}>
        <Input addonBefore="名称" value={whName} onChange={(e) => setWhName(e.target.value)} />
        <Input addonBefore="URL" placeholder="http://…" value={whUrl} onChange={(e) => setWhUrl(e.target.value)} />
        <Input addonBefore="Token" placeholder="Bearer，可留空" value={whToken} onChange={(e) => setWhToken(e.target.value)} />
        <Select value={whTrigger} style={{ width: 120 }} onChange={setWhTrigger} options={[
          { value: 'escalated', label: '顶出即推' }, { value: 'all', label: '全部' }, { value: 'manual', label: '仅手动' },
        ]} />
        <Button type="primary" onClick={() => save(async () => {
          if (!whUrl) { message.warning('请填 URL'); return; }
          await configApi.addWebhook({
            name: whName || 'webhook', url: whUrl, trigger: whTrigger, token: whToken, enabled: true, fields: whFields,
            headers: Object.fromEntries(whHeaders.filter(([k]) => k.trim())), body: whBody,
          });
          setWhName(''); setWhUrl(''); setWhTrigger('escalated'); setWhToken(''); setWhFields(ALL_FIELDS); setWhHeaders([]); setWhBody('');
        }, '已添加外发目标')}>添加</Button>
      </Space>
      <div style={{ marginTop: 12 }}>
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>自定义请求头（-H）</Typography.Text>
        <KeyValueMap entries={whHeaders} onChange={setWhHeaders} keyPh="Header" valPh="值" />
      </div>
      <div style={{ marginTop: 12 }}>
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>请求体模板（Jinja2，留空=默认固定信封）</Typography.Text>
        <Input.TextArea value={whBody} placeholder='如 {"content": {{ case | tojson }}}' onChange={(e) => setWhBody(e.target.value)} rows={3} style={{ marginTop: 4, fontFamily: 'monospace' }} />
      </div>
      <div style={{ marginTop: 12 }}>
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>外发字段（点选）— 仅请求体模板留空时生效</Typography.Text>
        {FIELD_GROUPS.map(([group, items]) => (
          <div key={group} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6, flexWrap: 'wrap' }}>
            <Typography.Text type="secondary" style={{ fontSize: 12, minWidth: 48 }}>{group}</Typography.Text>
            {items.map(([f, label]) => (
              <Tag.CheckableTag key={f} checked={whFields.includes(f)} onChange={() => setWhFields((s) => (s.includes(f) ? s.filter((x) => x !== f) : [...s, f]))}>
                {label}
              </Tag.CheckableTag>
            ))}
          </div>
        ))}
      </div>
    </Card>
  );

  const memoryTab = (
    <Card size="small" title="记忆管理">
      <Typography.Paragraph type="secondary">睡眠巩固沉淀的记忆与处置反馈，供系统2 研判时检索。判错的可在此删除或清空。</Typography.Paragraph>

      <Typography.Text strong>睡眠巩固记忆</Typography.Text>
      {memory === null ? <Typography.Paragraph type="secondary">加载中…</Typography.Paragraph> : memory.length === 0 ? <Typography.Paragraph type="secondary">暂无记忆</Typography.Paragraph> : (
        <>
          <Button danger size="small" style={{ margin: '8px 0' }} onClick={() => modal.confirm({ title: '清空全部睡眠巩固记忆？此操作不可撤销。', onOk: () => save(async () => { setMemory((await configApi.clearMemory()).items); }, '已清空记忆') })}>清空全部记忆</Button>
          {memory.map((m, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 0', borderBottom: '1px solid #f0f0f0' }}>
              <div style={{ flex: 1 }}>
                <div>{typeof m.summary === 'string' ? m.summary : JSON.stringify(m)}</div>
                {Array.isArray(m.ttps) && m.ttps.length > 0 && <div style={{ fontSize: 12, color: '#8a8f98' }}>手法：{m.ttps.join('、')}</div>}
                {Array.isArray(m.false_positives) && m.false_positives.length > 0 && <div style={{ fontSize: 12, color: '#8a8f98' }}>误报模式：{m.false_positives.join('、')}</div>}
              </div>
              <Button size="small" danger onClick={() => save(async () => { setMemory((await configApi.deleteMemory(i)).items); }, '已删除该记忆')}>删</Button>
            </div>
          ))}
        </>
      )}

      <Typography.Text strong style={{ display: 'block', marginTop: 16 }}>处置反馈</Typography.Text>
      {feedback === null ? <Typography.Paragraph type="secondary">加载中…</Typography.Paragraph> : feedback.length === 0 ? <Typography.Paragraph type="secondary">暂无反馈</Typography.Paragraph> : (
        <>
          <Button danger size="small" style={{ margin: '8px 0' }} onClick={() => modal.confirm({ title: '清空全部处置反馈？此操作不可撤销。', onOk: () => save(async () => { setFeedback((await configApi.clearFeedback()).items); }, '已清空反馈') })}>清空全部反馈</Button>
          {feedback.map((f, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 0', borderBottom: '1px solid #f0f0f0' }}>
              <div style={{ flex: 1 }}>
                <div>{f.type ?? 'feedback'}{f.reason ? `：${f.reason}` : ''}</div>
                <div style={{ fontSize: 12, color: '#8a8f98' }}>
                  {[f.asset, f.signal_type, f.case_uid, f.count !== undefined ? `count ${f.count}` : null, f.time].filter(Boolean).join(' · ')}
                </div>
              </div>
              <Button size="small" danger onClick={() => save(async () => { setFeedback((await configApi.deleteFeedback(i)).items); }, '已删除该反馈')}>删</Button>
            </div>
          ))}
        </>
      )}
    </Card>
  );

  if (ruleDetail) {
    return (
      <div>
        <Button icon={<ArrowLeftOutlined />} onClick={() => setRuleDetail(null)}>返回来源解析</Button>
        <Card size="small" title={`规则详情 · ${ruleDetail.source}${ruleDetail.isNew ? '（新增）' : ''}`} style={{ marginTop: 12, maxWidth: 760 }}>
          <Input.TextArea value={ruleDraft} onChange={(e) => setRuleDraft(e.target.value)} rows={16} style={{ fontFamily: 'monospace' }} />
          <Space style={{ marginTop: 12 }}>
            {!ruleDetail.isNew && <Button danger onClick={() => deleteRule(ruleDetail.source, ruleDetail.index)}>删除</Button>}
            <Button onClick={() => setRuleDetail(null)}>取消</Button>
            <Button type="primary" onClick={saveRuleDetail}>保存</Button>
          </Space>
        </Card>
      </div>
    );
  }

  return (
    <div>
      <Space style={{ marginBottom: 12 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={onBack}>返回设置</Button>
        <Typography.Title level={4} style={{ margin: 0 }}>高级设置</Typography.Title>
      </Space>
      <Tabs
        tabPosition="left"
        items={[
          { key: 'presets', label: '阈值配置（四档）', children: presetsTab },
          { key: 'model', label: '模型接入', children: modelTab },
          { key: 'freq', label: '频率降级', children: freqTab },
          { key: 'gating', label: '前额叶 唤醒门槛', children: gatingTab },
          { key: 'detection', label: '检测调参', children: detectionTab },
          { key: 'ingest', label: '数据接入（syslog）', children: ingestTab },
          { key: 'webhooks', label: '案件外发（Webhook）', children: webhooksTab },
          { key: 'memory', label: '记忆管理', children: memoryTab },
          { key: 'assets', label: '资产清单', children: assetsTab },
        ]}
      />
    </div>
  );
}
