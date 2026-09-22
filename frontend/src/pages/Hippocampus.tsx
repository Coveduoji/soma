import { useMemo, useState } from 'react';
import { Row, Col, Card, Select, Button, Listy, Typography, Segmented, Space, Spin } from 'antd';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { dashboardApi } from '../api/dashboard';
import HippocampusGraph, { type Sel } from '../components/graph/HippocampusGraph';
import { ENTITY_COLORS } from '../theme/tokens';
import { useTerms } from '../hooks/useTerms';

const TYPE_LABELS: [string, string][] = [
  ['asset', '实体（主机/账号）'],
  ['ip', 'IP 地址'],
  ['hash', '文件哈希'],
  ['domain', '域名'],
];

export default function Hippocampus() {
  const { t } = useTerms();
  const navigate = useNavigate();
  const [mode, setMode] = useState<'all' | 'ip' | 'entity'>('all');
  const [sel, setSel] = useState<Sel>(null);
  const [sourceFilter, setSourceFilter] = useState('');
  const [sort, setSort] = useState<'time' | 'confidence'>('time');

  const { data: graph } = useQuery({
    queryKey: ['hippocampus'],
    queryFn: dashboardApi.hippocampus,
  });

  const filtered = useMemo(() => {
    if (!graph) return null;
    let nodes = graph.nodes;
    if (mode === 'ip') nodes = nodes.filter((n) => n.type === 'ip');
    else if (mode === 'entity') nodes = nodes.filter((n) => n.type !== 'ip');
    const ids = new Set(nodes.map((n) => n.id));
    const edges = graph.edges.filter((e) => ids.has(e.source) && ids.has(e.target));
    return { nodes, edges };
  }, [graph, mode]);

  const params: Record<string, string> = { sort };
  if (sourceFilter) params.source = sourceFilter;
  if (sel) {
    if (sel.kind === 'node') {
      params.type = sel.type;
      params.value = sel.value;
    } else {
      params.type = sel.type1;
      params.value = sel.value1;
      params.type2 = sel.type2;
      params.value2 = sel.value2;
    }
  }

  const { data: events } = useQuery({
    queryKey: ['hippocampus-events', sel, sourceFilter, sort],
    queryFn: () => dashboardApi.hippocampusEvents(params),
    enabled: !!sel,
  });

  return (
    <div>
      <Space style={{ marginBottom: 16 }} wrap>
        <Typography.Title level={4} style={{ margin: 0 }}>
          {t('hippocampus')}{' '}
          <Typography.Text type="secondary" style={{ fontSize: 14 }}>
            实体关联 · {graph?.nodes.length ?? 0} 实体 · {graph?.edges.length ?? 0} 关联
          </Typography.Text>
        </Typography.Title>
        <Segmented
          value={mode}
          onChange={(v) => setMode(v as 'all' | 'ip' | 'entity')}
          options={[
            { label: '全部', value: 'all' },
            { label: 'IP 模式', value: 'ip' },
            { label: '实体模式', value: 'entity' },
          ]}
        />
      </Space>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={16}>
          <Card size="small">
            {filtered && filtered.nodes.length > 0 ? (
              <>
                <HippocampusGraph nodes={filtered.nodes} edges={filtered.edges} onSelect={setSel} />
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 14, marginTop: 10, fontSize: 12, color: '#8a8f98' }}>
                  {TYPE_LABELS.map(([type, label]) => (
                    <span key={type} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                      <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: '50%', background: ENTITY_COLORS[type] }} />
                      {label}
                    </span>
                  ))}
                </div>
              </>
            ) : (
              <Typography.Text type="secondary">暂无图数据，先接入告警。</Typography.Text>
            )}
          </Card>
        </Col>

        <Col xs={24} lg={8}>
          <Card size="small" title={sel ? (sel.kind === 'node' ? sel.value : `${sel.value1} — ${sel.value2}`) : '关联事件'} style={{ maxHeight: 680, overflow: 'auto' }}>
            {!sel ? (
              <Typography.Text type="secondary">点一个节点或边，查看它的全部关联事件。</Typography.Text>
            ) : (
              <>
                <Space style={{ marginBottom: 12 }} wrap>
                  <Select
                    value={sourceFilter || undefined} placeholder="全部来源" style={{ width: 140 }} allowClear size="small"
                    onChange={(v) => setSourceFilter(v || '')}
                    options={(events?.sources ?? []).map((s) => ({ value: s, label: s }))}
                  />
                  <Select
                    value={sort} style={{ width: 110 }} size="small" onChange={(v) => setSort(v)}
                    options={[{ value: 'time', label: '按时间' }, { value: 'confidence', label: '按置信度' }]}
                  />
                  <Typography.Text type="secondary">共 {events?.total ?? 0} 条</Typography.Text>
                </Space>
                {!events ? (
                  <div style={{ padding: 24, textAlign: 'center' }}><Spin /></div>
                ) : (
                  <Listy
                    items={events.items}
                    rowKey={(e) => e.id}
                    itemRender={(e) => (
                      <div style={{ padding: '6px 0' }}>
                        <div style={{ fontSize: 12, color: '#8a8f98' }}>
                          [{e.time}] {e.source}/{e.type} · conf {e.confidence?.toFixed(2)}
                        </div>
                        <div style={{ fontSize: 13, wordBreak: 'break-all' }}>{e.raw}</div>
                        <div style={{ fontSize: 12 }}>
                          案件{' '}
                          <Typography.Text code style={{ cursor: 'pointer', color: '#2a78d6' }} onClick={() => navigate(`/cases/${e.case_id}`)}>
                            {e.case_uid}
                          </Typography.Text>
                        </div>
                      </div>
                    )}
                  />
                )}
              </>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}
