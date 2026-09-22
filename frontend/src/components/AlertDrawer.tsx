import { useEffect, useState } from 'react';
import { Drawer, Button, Space, Tag, Typography, Spin, Divider, App } from 'antd';
import { dashboardApi } from '../api/dashboard';
import { errMsg } from '../api/http';
import { verdictLabel } from '../lib/labels';
import ReportView from './report/ReportView';
import type { Report } from '../types/models';

// 告警核心字段（案件时间线 Alert 与丘脑 RawAlert 的公共子集）
export interface AlertInfo {
  id: number;
  time: string;
  source: string;
  asset: string;
  type: string;
  raw: string;
  confidence: number | null;
  reason: string;
  innate: number;
  verdict?: string;
  suppressed?: number;
  why?: string;
}

export default function AlertDrawer({ alert, open, onClose }: {
  alert: AlertInfo | null;
  open: boolean;
  onClose: () => void;
}) {
  const { message } = App.useApp();
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(false);

  // 切换告警时清掉上一次的研判结果
  useEffect(() => {
    setReport(null);
    setLoading(false);
  }, [alert?.id]);

  const analyze = async () => {
    if (!alert) return;
    setLoading(true);
    setReport(null);
    try {
      setReport(await dashboardApi.analyzeAlert(alert.id));
    } catch (e) {
      message.error(errMsg(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Drawer title="告警详情" width={560} open={open} onClose={onClose}>
      {alert && (
        <Space direction="vertical" size={10} style={{ width: '100%' }}>
          <div style={{ fontSize: 12, color: '#8a8f98' }}>
            [{alert.time}] {alert.source}/{alert.type} · conf {alert.confidence?.toFixed(2) ?? '—'}
          </div>
          <div>
            <Typography.Text type="secondary">资产 </Typography.Text>
            <Typography.Text>{alert.asset}</Typography.Text>
            {alert.innate ? <Tag color="blue" style={{ marginLeft: 6 }}>固有免疫</Tag> : null}
            {alert.suppressed ? <Tag style={{ marginLeft: 6 }}>被抑制</Tag> : null}
            {alert.verdict ? <Tag color="green" style={{ marginLeft: 6 }}>{verdictLabel(alert.verdict)}</Tag> : null}
          </div>
          {alert.reason && <Typography.Text type="secondary">初筛理由：{alert.reason}</Typography.Text>}
          {alert.why && <Typography.Text type="secondary">抑制原因：{alert.why}</Typography.Text>}
          <div style={{ wordBreak: 'break-all', background: '#f6f7f9', padding: 10, borderRadius: 6, fontSize: 12, fontFamily: 'monospace' }}>
            {alert.raw}
          </div>

          <Divider style={{ margin: '4px 0' }} />

          <Button type="primary" loading={loading} onClick={analyze}>AI 研判</Button>

          {loading ? (
            <div style={{ textAlign: 'center', padding: 24 }}><Spin /></div>
          ) : (
            <ReportView report={report} />
          )}
        </Space>
      )}
    </Drawer>
  );
}
