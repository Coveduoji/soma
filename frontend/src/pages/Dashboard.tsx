import { useState } from 'react';
import { Row, Col, Card, Statistic, Progress, Button, Typography, Select, DatePicker } from 'antd';
import dayjs from 'dayjs';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { dashboardApi } from '../api/dashboard';
import TrendChart from '../components/TrendChart';
import DeviceTrafficChart from '../components/DeviceTrafficChart';
import DeviceClassChart from '../components/DeviceClassChart';
import ExportReport from '../components/report/ExportReport';
import { useTerms } from '../hooks/useTerms';

export default function Dashboard() {
  const { t } = useTerms();
  const navigate = useNavigate();
  const [timeRange, setTimeRange] = useState<[number, number]>([
    dayjs().subtract(24, 'hour').unix(),
    dayjs().unix(),
  ]);
  const [devSource, setDevSource] = useState('');
  const [exportOpen, setExportOpen] = useState(false);

  const { data: d } = useQuery({
    queryKey: ['dashboard'],
    queryFn: dashboardApi.dashboard,
    refetchInterval: 15000,
  });

  const { data: trend } = useQuery({
    queryKey: ['trend', timeRange],
    queryFn: () => dashboardApi.trend(timeRange[0], timeRange[1]),
    refetchInterval: 15000,
  });

  const { data: devTraffic } = useQuery({
    queryKey: ['device-traffic', timeRange],
    queryFn: () => dashboardApi.deviceTraffic(timeRange[0], timeRange[1]),
    refetchInterval: 15000,
  });

  const { data: devClass } = useQuery({
    queryKey: ['device-classification', devSource, timeRange],
    queryFn: () => dashboardApi.deviceClassification(devSource, timeRange[0], timeRange[1]),
    refetchInterval: 15000,
  });

  if (!d) return <Card loading />;

  const { counts, tolerance, innate } = d;
  const total = Math.max(1, counts.alerts);
  const denoise = counts.alerts > 0 ? Math.round(((counts.alerts - counts.reports) / counts.alerts) * 100) : 0;

  const kpis = [
    { title: '案件', value: counts.cases, sub: '已归案', to: '/triage' },
    { title: '告警', value: counts.alerts, sub: `上板 ${counts.surfaced} · 抑制 ${counts.suppressed}`, to: '/thalamus' },
    { title: '被抑制', value: counts.suppressed, sub: '留痕可研判', to: '/thalamus' },
    { title: '深度分析', value: counts.reports, sub: `唤醒 ${counts.reports} 次`, to: '/triage' },
    { title: '实体', value: counts.artifacts, sub: '图节点', to: '/hippocampus' },
    { title: '攻击链', value: counts.attack_chains, sub: '已拼链', to: '/triage' },
    { title: t('tolerance'), value: tolerance.length, sub: '白名单', to: '/immune' },
    { title: t('innate'), value: innate.length, sub: '规则', to: '/immune' },
  ];

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 16, gap: 12, flexWrap: 'wrap' }}>
        <Typography.Title level={4} style={{ margin: 0 }}>{t('dashboard')}</Typography.Title>
        <div style={{ flex: 1 }} />
        <DatePicker.RangePicker
          showTime
          value={[dayjs(timeRange[0] * 1000), dayjs(timeRange[1] * 1000)]}
          presets={[
            { label: '近24小时', value: [dayjs().subtract(24, 'hour'), dayjs()] },
            { label: '近7天', value: [dayjs().subtract(7, 'day'), dayjs()] },
            { label: '近30天', value: [dayjs().subtract(30, 'day'), dayjs()] },
          ]}
          onChange={(v) => {
            if (v && v[0] && v[1]) setTimeRange([v[0].unix(), v[1].unix()]);
          }}
        />
        <Button type="primary" onClick={() => setExportOpen(true)}>导出报告</Button>
      </div>

      <Row gutter={[16, 16]}>
        {kpis.map((k) => (
          <Col xs={12} sm={12} md={6} key={k.title}>
            <Card hoverable onClick={() => navigate(k.to)} size="small">
              <Statistic title={k.title} value={k.value} />
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>{k.sub}</Typography.Text>
            </Card>
          </Col>
        ))}
      </Row>

      <Card style={{ marginTop: 16 }} title="告警降噪">
        <div style={{ display: 'flex', alignItems: 'center', gap: 24, marginBottom: 16 }}>
          <Statistic title="降噪率" value={denoise} suffix="%" />
          <Typography.Text type="secondary">
            {counts.alerts} 条告警 → {counts.reports} 条需深度分析
          </Typography.Text>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, maxWidth: 560 }}>
          <Progress percent={100} format={() => `告警 ${counts.alerts}`} />
          <Progress percent={Math.round((counts.cases / total) * 100)} strokeColor="#2a78d6" format={() => `归案 ${counts.cases}`} />
          <Progress percent={Math.round((counts.reports / total) * 100)} strokeColor="#1baf7a" format={() => `深度分析 ${counts.reports}`} />
        </div>
        <Typography.Paragraph type="secondary" style={{ marginTop: 12, marginBottom: 0 }}>
          把 {counts.alerts} 条告警聚合为 {counts.cases} 个案件，仅 {counts.reports} 个需要深度分析。
        </Typography.Paragraph>
      </Card>

      <Card style={{ marginTop: 16 }} title="流量趋势">
        {trend && <TrendChart buckets={trend.buckets} />}
      </Card>

      <Card style={{ marginTop: 16 }} title="设备流量">
        <Row gutter={[16, 16]}>
          {(devTraffic?.sources ?? []).map((src) => (
            <Col xs={24} lg={12} key={src}>
              <Card size="small" title={src}>
                <DeviceTrafficChart items={devTraffic!.items.filter((i) => i.source === src)} />
              </Card>
            </Col>
          ))}
        </Row>
      </Card>

      <Card
        style={{ marginTop: 16 }}
        title="告警分类"
        extra={
          <Select
            value={devSource}
            style={{ width: 180 }}
            onChange={(v) => setDevSource(v)}
            options={[
              { value: '', label: '全部设备' },
              ...(devTraffic?.sources ?? []).map((s) => ({ value: s, label: s })),
            ]}
          />
        }
      >
        {devClass && <DeviceClassChart items={devClass.items} />}
      </Card>

      <ExportReport open={exportOpen} onClose={() => setExportOpen(false)} sources={devTraffic?.sources} />
    </div>
  );
}
