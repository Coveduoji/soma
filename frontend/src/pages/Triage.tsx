import { useState } from 'react';
import { Table, Input, Select, Checkbox, Tag, Button, Space, App, Typography, Flex } from 'antd';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { casesApi } from '../api/cases';
import { statusLabel, verdictLabel } from '../lib/labels';
import { useTerms } from '../hooks/useTerms';
import type { Case } from '../types/models';

const PAGE_SIZE = 20;
const STATUSES = ['New', 'In Progress', 'On Hold', 'Resolved', 'Closed'];
const VERDICTS = ['True Positive', 'Suspicious', 'False Positive', 'Benign', 'Insufficient Data'];

function riskTag(r: number | undefined) {
  const v = r ?? 0;
  if (v >= 0.3) return <Tag color="red">高</Tag>;
  if (v >= 0.1) return <Tag color="orange">中</Tag>;
  return <Tag>低</Tag>;
}

export default function Triage() {
  const { t } = useTerms();
  const navigate = useNavigate();
  const { message, modal } = App.useApp();
  const [status, setStatus] = useState('');
  const [verdict, setVerdict] = useState('');
  const [risk, setRisk] = useState('');
  const [pending, setPending] = useState(true);
  const [q, setQ] = useState('');
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<number[]>([]);
  const [bulkReason, setBulkReason] = useState('');

  const params = new URLSearchParams();
  if (status) params.set('status', status);
  if (verdict) params.set('verdict', verdict);
  if (risk) params.set('risk', risk);
  if (pending) params.set('pending', '1');
  if (q.trim()) params.set('q', q.trim());
  params.set('limit', String(PAGE_SIZE));
  params.set('offset', String(page * PAGE_SIZE));
  const queryStr = params.toString();

  const { data, isLoading } = useQuery({
    queryKey: ['cases', status, verdict, pending, q, risk, page],
    queryFn: () => casesApi.listCases(queryStr),
    refetchInterval: 15000,
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;

  const selectable = items.filter((c) => !c.verdict);

  const bulkFP = () => {
    if (selected.length === 0) return;
    modal.confirm({
      title: `确定将 ${selected.length} 个案件批量标记为误报？`,
      content: '其签名将写进免疫耐受白名单，以后同形状告警将被降级。',
      onOk: async () => {
        await casesApi.bulkFalsePositive(selected, bulkReason);
        message.success(`已批量标记 ${selected.length} 个案件为误报`);
        setSelected([]);
        setBulkReason('');
      },
    });
  };

  const columns = [
    {
      title: '案件',
      dataIndex: 'correlation_uid',
      render: (v: string) => <Typography.Text code>{v}</Typography.Text>,
    },
    {
      title: '实体',
      dataIndex: 'entities',
      render: (es: { type: string; value: string }[]) => es.map((e) => e.value).join(' · '),
    },
    { title: '风险', dataIndex: 'risk', width: 90, render: (r: number | undefined) => riskTag(r) },
    {
      title: '状态',
      dataIndex: 'status',
      width: 120,
      render: (s: string) => <Tag color={s === 'Closed' ? 'green' : 'default'}>{statusLabel(s || 'New')}</Tag>,
    },
    { title: '结论', dataIndex: 'verdict', width: 120, render: (v: string) => verdictLabel(v) },
  ];

  return (
    <div>
      <Flex justify="space-between" align="center" style={{ marginBottom: 16 }} wrap gap={12}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          {t('triage')} <Typography.Text type="secondary" style={{ fontSize: 14 }}>{total} 个案件 · 按强度排序</Typography.Text>
        </Typography.Title>
        <Space wrap>
          <Input.Search
            placeholder="搜索案件 ID / 标题 / 实体…"
            allowClear
            style={{ width: 220 }}
            onSearch={(v) => { setQ(v); setPage(0); }}
          />
          <Checkbox checked={pending} onChange={(e) => { setPending(e.target.checked); setPage(0); }}>
            只看待处理
          </Checkbox>
          <Select
            value={risk || undefined} placeholder="全部风险" style={{ width: 150 }} allowClear
            onChange={(v) => { setRisk(v || ''); setPage(0); }}
            options={[
              { value: 'high', label: '高风险 ≥0.3' },
              { value: 'mid', label: '中风险 0.1~0.3' },
              { value: 'low', label: '低风险 <0.1' },
            ]}
          />
          <Select
            value={status || undefined} placeholder="全部状态" style={{ width: 130 }} allowClear
            onChange={(v) => { setStatus(v || ''); setPage(0); }}
            options={STATUSES.map((s) => ({ value: s, label: statusLabel(s) }))}
          />
          <Select
            value={verdict || undefined} placeholder="全部结论" style={{ width: 130 }} allowClear
            onChange={(v) => { setVerdict(v || ''); setPage(0); }}
            options={VERDICTS.map((v) => ({ value: v, label: verdictLabel(v) }))}
          />
          <Input
            placeholder="批量处置理由（可选）" style={{ width: 180 }} value={bulkReason}
            onChange={(e) => setBulkReason(e.target.value)}
          />
          <Button danger disabled={selected.length === 0} onClick={bulkFP}>
            批量标记误报（{selected.length}）
          </Button>
        </Space>
      </Flex>

      <Table<Case>
        rowKey="id"
        loading={isLoading}
        dataSource={items}
        columns={columns}
        onRow={(record) => ({ onClick: () => navigate(`/cases/${record.id}`), style: { cursor: 'pointer' } })}
        rowSelection={{
          selectedRowKeys: selected,
          onChange: (keys) => setSelected(keys as number[]),
          getCheckboxProps: (record) => ({ disabled: !!record.verdict }),
        }}
        pagination={{
          current: page + 1,
          pageSize: PAGE_SIZE,
          total,
          onChange: (p) => setPage(p - 1),
          showSizeChanger: false,
          showTotal: (t) => `共 ${t} 个案件`,
        }}
      />
    </div>
  );
}
