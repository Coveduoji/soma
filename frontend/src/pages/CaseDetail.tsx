import { useEffect, useState } from 'react';
import { Card, Row, Col, Space, Typography, Tag, Button, Select, Input, Listy, App, Divider, Flex, Tooltip } from 'antd';
import { ArrowLeftOutlined, ShareAltOutlined, ExportOutlined } from '@ant-design/icons';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { casesApi } from '../api/cases';
import EntityGraph from '../components/graph/EntityGraph';
import ReportView from '../components/report/ReportView';
import AlertDrawer, { type AlertInfo } from '../components/AlertDrawer';
import { statusLabel, verdictLabel } from '../lib/labels';
import { errMsg } from '../api/http';
import type { Case, Alert } from '../types/models';

const VERDICTS = ['True Positive', 'Suspicious', 'False Positive', 'Benign', 'Insufficient Data'];

export default function CaseDetail() {
  const { id } = useParams();
  const caseId = Number(id);
  const navigate = useNavigate();
  const { message, modal } = App.useApp();

  const [verdict, setVerdict] = useState('');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [selectedAlert, setSelectedAlert] = useState<number | null>(null);
  const [selectedEntity, setSelectedEntity] = useState<{ type: string; value: string } | null>(null);
  const [related, setRelated] = useState<Case[] | null>(null);
  const [analyzingCase, setAnalyzingCase] = useState(false);
  const [drawerAlert, setDrawerAlert] = useState<AlertInfo | null>(null);

  const { data, refetch } = useQuery({
    queryKey: ['case', caseId],
    queryFn: () => casesApi.getCase(caseId),
    enabled: !!caseId,
  });
  const { data: graph } = useQuery({
    queryKey: ['case-hippocampus', caseId],
    queryFn: () => casesApi.caseHippocampus(caseId),
    enabled: !!caseId,
  });

  useEffect(() => {
    if (data) setVerdict(data.case.verdict || '');
  }, [data]);

  useEffect(() => {
    setRelated(null);
    setSelectedAlert(null);
    setSelectedEntity(null);
  }, [caseId]);

  if (!data) return <Card loading />;

  const { case: c, alerts, report } = data;
  const selected = alerts.find((a) => a.id === selectedAlert);
  const highlight = selected?.artifacts ?? (selectedEntity ? [selectedEntity] : undefined);

  const isAlertHighlighted = (a: Alert) =>
    a.id === selectedAlert ||
    (selectedEntity != null && a.artifacts.some((art) => art.type === selectedEntity.type && art.value === selectedEntity.value));

  const toggleSelect = (alertId: number) => {
    setSelectedAlert((cur) => (cur === alertId ? null : alertId));
    setSelectedEntity(null);
  };

  const onNodeTap = (type: string, value: string) => {
    casesApi.entityCases(type, value).then(setRelated);
    setSelectedEntity((cur) => (cur && cur.type === type && cur.value === value ? null : { type, value }));
    setSelectedAlert(null);
  };

  const refresh = () => refetch();

  const analyzeCaseNow = async () => {
    setAnalyzingCase(true);
    try {
      await casesApi.analyzeCase(caseId);
      message.success('AI 研判完成');
      refresh();
    } catch (e) {
      message.error(errMsg(e));
    } finally {
      setAnalyzingCase(false);
    }
  };

  const saveVerdict = async () => {
    if (!verdict) return;
    setBusy(true);
    try {
      if (verdict === 'False Positive') {
        modal.confirm({
          title: '标记为误报',
          content: '该案签名将写进免疫耐受白名单，以后同形状告警将被静默。确定？',
          onOk: async () => {
            const r = await casesApi.falsePositive(caseId, note);
            message.success(`已标记误报，记住 ${r.learned.length} 条免疫耐受规则`);
            refresh();
          },
        });
      } else if (verdict === 'True Positive') {
        modal.confirm({
          title: '标记为真阳性',
          content: '该案签名将写进固有免疫规则，以后同形状告警将边缘秒拦。确定？',
          onOk: async () => {
            const r = await casesApi.truePositive(caseId, note);
            message.success(`已标记真阳性，记住 ${r.learned.length} 条固有免疫规则`);
            refresh();
          },
        });
      } else {
        const body: { verdict: string; note: string; status?: string } = { verdict, note };
        if (verdict === 'Insufficient Data') body.status = 'On Hold';
        await casesApi.patchCase(caseId, body);
        message.success('已保存结论');
        refresh();
      }
    } catch (e) {
      message.error(errMsg(e));
    } finally {
      setBusy(false);
    }
  };

  const markAlert = (alertId: number, v: string) => {
    const isFP = v === 'False Positive';
    modal.confirm({
      title: isFP ? '把这条告警写进免疫耐受白名单？' : '把这条告警写进固有免疫规则？',
      onOk: async () => {
        await casesApi.alertDisposition(alertId, v);
        message.success(isFP ? '已标记该条告警为误报' : '已标记该条告警为真阳性');
        refresh();
      },
    });
  };

  const patch = async (body: object) => {
    setBusy(true);
    try {
      await casesApi.patchCase(caseId, { ...body, note });
      message.success('已更新');
      refresh();
    } catch (e) {
      message.error(errMsg(e));
    } finally {
      setBusy(false);
    }
  };

  const pushCase = async () => {
    setBusy(true);
    try {
      const r = await casesApi.pushCase(caseId);
      const ok = r.results.filter((x) => x.ok).length;
      message.success(`外发完成：${ok}/${r.results.length} 个目标成功`);
    } catch (e) {
      message.error('外发失败：' + errMsg(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Space orientation="vertical" size={16} style={{ width: '100%' }}>
      <Flex gap={8}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/triage')}>返回队列</Button>
        <Button icon={<ShareAltOutlined />} onClick={() => navigate('/hippocampus')}>在海马体查看</Button>
      </Flex>

      <div>
        <Typography.Title level={4} style={{ margin: 0 }}>
          <Typography.Text code>{c.correlation_uid}</Typography.Text>
        </Typography.Title>
        <Typography.Text type="secondary">
          风险 {c.risk?.toFixed(2) ?? '—'}
          {c.risk_incomplete && (
            <Tooltip title="风险分不全：缺攻击结果/威胁等级，按保守默认估算">
              <Tag color="warning" style={{ marginInlineEnd: 0, marginLeft: 6 }}>不全</Tag>
            </Tooltip>
          )}
          {' '}· 强度 {c.strength.toFixed(2)} · {alerts.length} 条告警
        </Typography.Text>
      </div>

      <Card title="攻击链" size="small">
        {alerts.length === 0 ? (
          <Typography.Text type="secondary">无告警</Typography.Text>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', gap: 4, overflowX: 'auto', padding: '6px 0' }}>
            {alerts.map((a, i) => (
              <Flex key={a.id} align="center" gap={4} style={{ flexShrink: 0 }}>
                <div
                  onClick={() => toggleSelect(a.id)}
                  style={{
                    padding: '8px 12px', borderRadius: 8, cursor: 'pointer', minWidth: 130,
                    border: isAlertHighlighted(a) ? '2px solid #2a78d6' : '1px solid #e4e7eb',
                    background: isAlertHighlighted(a) ? '#e3eefc' : undefined,
                  }}
                >
                  <div style={{ fontSize: 11, color: '#8a8f98' }}>{a.time}</div>
                  <div style={{ fontSize: 13, fontWeight: 600 }}>{a.source}/{a.type}</div>
                  <div style={{ fontSize: 12, color: '#4d5158', wordBreak: 'break-all' }}>{a.asset}</div>
                  <div style={{ fontSize: 11, color: '#2a78d6' }}>conf {a.confidence?.toFixed(2)}</div>
                </div>
                {i < alerts.length - 1 && <span style={{ color: '#8a8f98' }}>→</span>}
              </Flex>
            ))}
          </div>
        )}
      </Card>

      <Row gutter={[16, 16]}>
        <Col xs={24} md={8}>
          <Card title="告警时间线" size="small">
            <Listy
              items={alerts}
              rowKey={(a) => a.id}
              itemRender={(a) => (
                <div
                  onClick={() => toggleSelect(a.id)}
                  style={{ cursor: 'pointer', background: isAlertHighlighted(a) ? '#e3eefc' : undefined, padding: '8px 12px' }}
                >
                  <div style={{ fontSize: 12, color: '#8a8f98' }}>
                    [{a.time}] {a.source}/{a.type} · conf {a.confidence?.toFixed(2)}
                    {a.innate ? ' · 固有免疫秒拦' : ''}
                    {a.verdict && <Tag style={{ marginLeft: 6 }}>{verdictLabel(a.verdict)}</Tag>}
                  </div>
                  <div style={{ fontSize: 13, marginTop: 2, wordBreak: 'break-all' }}>{a.raw}</div>
                  <Space size={6} style={{ marginTop: 6 }}>
                    <Button size="small" disabled={busy} onClick={(e) => { e.stopPropagation(); markAlert(a.id, 'False Positive'); }}>误报</Button>
                    <Button size="small" disabled={busy} onClick={(e) => { e.stopPropagation(); markAlert(a.id, 'True Positive'); }}>真阳性</Button>
                    <Button size="small" onClick={(e) => { e.stopPropagation(); setDrawerAlert(a); }}>详情</Button>
                  </Space>
                </div>
              )}
            />
          </Card>
        </Col>

        <Col xs={24} md={8}>
          <Card title="实体图" size="small">
            {graph ? <EntityGraph graph={graph} onNodeTap={onNodeTap} highlight={highlight} /> : <div style={{ height: 320 }} />}
            <div style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {c.entities.map((e, i) => (
                <Tag key={i}>{e.type}:{e.value}</Tag>
              ))}
            </div>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>点实体高亮相关告警并反查关联案件</Typography.Text>
            {related !== null && (
              <div style={{ marginTop: 8 }}>
                <Divider style={{ margin: '8px 0' }} />
                <Typography.Text type="secondary">关联案件（{related.length}）</Typography.Text>
                {related.map((rc) => (
                  <div key={rc.id} style={{ cursor: 'pointer', padding: '4px 0' }} onClick={() => navigate(`/cases/${rc.id}`)}>
                    <Typography.Text code style={{ color: '#2a78d6' }}>{rc.correlation_uid}</Typography.Text>
                    {' '}· 强度 {rc.strength.toFixed(2)} · {statusLabel(rc.status || 'New')}
                  </div>
                ))}
                {related.length === 0 && <Typography.Text type="secondary">无其他关联案件</Typography.Text>}
              </div>
            )}
          </Card>
        </Col>

        <Col xs={24} md={8}>
          <Card
            title={<Space>AI 调查报告 <Button size="small" loading={analyzingCase} onClick={analyzeCaseNow}>AI 研判</Button></Space>}
            size="small"
          >
            <ReportView report={report} />
          </Card>
        </Col>
      </Row>

      <Card size="small">
        <Flex gap={8} wrap align="center">
          <Input
            placeholder="处置理由（为什么这么判）" style={{ flex: 1, minWidth: 200 }} value={note}
            onChange={(e) => setNote(e.target.value)}
          />
          <Select
            value={verdict || undefined} placeholder="设置结论…" style={{ width: 160 }}
            onChange={(v) => setVerdict(v)}
            options={VERDICTS.map((v) => ({ value: v, label: verdictLabel(v) }))}
          />
          <Button disabled={!verdict || busy} onClick={saveVerdict}>保存结论</Button>
          {c.status === 'Closed' ? (
            <Button type="primary" disabled={busy} onClick={() => patch({ status: 'In Progress' })}>重启</Button>
          ) : (
            <Button disabled={busy} onClick={() => patch({ status: 'Closed' })}>关闭案件</Button>
          )}
          <Button disabled={busy} onClick={pushCase}>外发</Button>
          <Button icon={<ExportOutlined />} onClick={() => casesApi.exportCase(caseId).catch((e) => message.error(errMsg(e)))}>导出报告</Button>
        </Flex>
      </Card>

      <AlertDrawer alert={drawerAlert} open={drawerAlert !== null} onClose={() => setDrawerAlert(null)} />
    </Space>
  );
}
