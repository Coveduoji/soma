import { useState } from 'react';
import { Row, Col, Card, Listy, Input, Select, Tag, Button, Typography, Space, App, Pagination, Spin } from 'antd';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { dashboardApi } from '../api/dashboard';
import { useTerms } from '../hooks/useTerms';
import { errMsg } from '../api/http';
import type { RawAlert } from '../types/models';
import AlertDrawer, { type AlertInfo } from '../components/AlertDrawer';

export default function Thalamus() {
  const { t } = useTerms();
  const navigate = useNavigate();
  const { message } = App.useApp();
  const [q, setQ] = useState('');
  const [source, setSource] = useState('');
  const [suppressed, setSuppressed] = useState('');
  const [sort, setSort] = useState<'time' | 'confidence'>('time');
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(50);
  const [drawerAlert, setDrawerAlert] = useState<AlertInfo | null>(null);

  const params: Record<string, string> = { sort, limit: String(pageSize), offset: String(page * pageSize) };
  if (q.trim()) params.q = q.trim();
  if (source) params.source = source;
  if (suppressed) params.suppressed = suppressed;

  const { data } = useQuery({
    queryKey: ['thalamus', q, source, suppressed, sort, page, pageSize],
    queryFn: () => dashboardApi.thalamus(params),
    refetchInterval: 15000,
  });
  const { data: audit } = useQuery({
    queryKey: ['audit'],
    queryFn: dashboardApi.audit,
  });

  const total = data?.total ?? 0;

  const restore = async (id: number) => {
    try {
      const r = await dashboardApi.restore(id);
      message.success('已放回');
      navigate(`/cases/${r.case_id}`);
    } catch (e) {
      message.error(errMsg(e));
    }
  };

  return (
    <div>
      <Space style={{ marginBottom: 16 }} wrap>
        <Typography.Title level={4} style={{ margin: 0 }}>
          {t('thalamus')} <Typography.Text type="secondary" style={{ fontSize: 14 }}>原始信号流 · {total} 条</Typography.Text>
        </Typography.Title>
      </Space>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={15}>
          <Card
            size="small"
            title={
              <Space wrap>
                <Input.Search
                  placeholder="搜索 raw / 主体 / 类型…" allowClear style={{ width: 200 }}
                  onSearch={(v) => { setQ(v); setPage(0); }}
                />
                <Select
                  value={source || undefined} placeholder="全部来源" style={{ width: 140 }} allowClear
                  onChange={(v) => { setSource(v || ''); setPage(0); }}
                  options={(data?.sources ?? []).map((s) => ({ value: s, label: s }))}
                />
                <Select
                  value={suppressed || undefined} placeholder="全部（含被抑制）" style={{ width: 150 }} allowClear
                  onChange={(v) => { setSuppressed(v || ''); setPage(0); }}
                  options={[
                    { value: '0', label: '仅上板' },
                    { value: '1', label: '仅被抑制' },
                  ]}
                />
                <Select
                  value={sort} style={{ width: 110 }}
                  onChange={(v) => setSort(v)}
                  options={[
                    { value: 'time', label: '按时间' },
                    { value: 'confidence', label: '按置信度' },
                  ]}
                />
              </Space>
            }
          >
            {!data ? (
              <div style={{ padding: 24, textAlign: 'center' }}><Spin /></div>
            ) : (
              <>
                <Listy<RawAlert>
                  items={data.items}
                  rowKey={(a) => a.id}
                  itemRender={(a) => (
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '8px 0' }}>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontSize: 12, color: '#8a8f98' }}>
                          [{a.time}] {a.source}/{a.type} · conf {a.confidence?.toFixed(2) ?? '—'}
                          {a.suppressed ? <Tag style={{ marginLeft: 6 }}>被抑制</Tag> : null}
                          {a.innate ? <Tag color="blue" style={{ marginLeft: 6 }}>固有免疫</Tag> : null}
                        </div>
                        <div style={{ fontSize: 13, marginTop: 2, wordBreak: 'break-all' }}>{a.raw}</div>
                        {a.suppressed && a.why ? <div style={{ fontSize: 12, color: '#8a8f98', wordBreak: 'break-all' }}>原因：{a.why}</div> : null}
                        {a.case_uid ? (
                          <div style={{ fontSize: 12 }}>
                            案件{' '}
                            <Typography.Text code style={{ cursor: 'pointer', color: '#2a78d6' }} onClick={() => navigate(`/cases/${a.case_id!}`)}>
                              {a.case_uid}
                            </Typography.Text>
                          </div>
                        ) : null}
                      </div>
                      <Space size={4}>
                        {a.suppressed && <Button size="small" onClick={() => restore(a.id)}>放回</Button>}
                        <Button size="small" onClick={() => setDrawerAlert(a)}>详情</Button>
                      </Space>
                    </div>
                  )}
                />
                {total > 0 && (
                  <Pagination
                    style={{ marginTop: 12, textAlign: 'center' }}
                    current={page + 1}
                    pageSize={pageSize}
                    total={total}
                    onChange={(p) => setPage(p - 1)}
                    showSizeChanger
                    pageSizeOptions={[20, 50, 100, 200]}
                    onShowSizeChange={(_c, size) => { setPageSize(size); setPage(0); }}
                  />
                )}
              </>
            )}
          </Card>
        </Col>

        <Col xs={24} lg={9}>
          <Card size="small" title="决策留痕（为什么没深想 / 为什么被拦）">
            <div style={{ maxHeight: 'calc(100vh - 200px)', overflowY: 'auto' }}>
              {!audit ? (
                <Typography.Text type="secondary">加载中…</Typography.Text>
              ) : audit.items.length === 0 ? (
                <Typography.Text type="secondary">暂无留痕。</Typography.Text>
              ) : (
                <Listy
                  items={audit.items}
                  rowKey={(x) => x.id}
                  itemRender={(x) => (
                    <div style={{ padding: '6px 0' }}>
                      <div style={{ fontSize: 12, color: '#8a8f98' }}>
                        [{x.created_at}] <b>{x.action}</b> · {x.entity}
                      </div>
                      <div style={{ fontSize: 13, wordBreak: 'break-all' }}>{x.changes}</div>
                    </div>
                  )}
                />
              )}
            </div>
          </Card>
        </Col>
      </Row>

      <AlertDrawer alert={drawerAlert} open={drawerAlert !== null} onClose={() => setDrawerAlert(null)} />
    </div>
  );
}
