import { Column, Line } from '@ant-design/plots';
import { Empty, Space, Typography } from 'antd';

interface Bucket {
  label: string;
  count: number;
  tp: number;
  fp: number;
  tp_rate: number | null;
}

export default function ConfidenceChart({ buckets, thresholds }: {
  buckets: Bucket[];
  thresholds: { suppress_below: number; escalate_above: number };
}) {
  if (!buckets || buckets.length === 0) return <Empty description="暂无上板告警数据" />;

  const histData = buckets.map((b) => ({ label: b.label, value: b.count }));
  const calData = buckets
    .filter((b) => b.tp_rate !== null)
    .map((b) => ({ label: b.label, value: b.tp_rate }));

  return (
    <Space direction="vertical" size={8} style={{ width: '100%' }}>
      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
        置信度分布 · 抑制线 {thresholds.suppress_below} / 顶出线 {thresholds.escalate_above}
      </Typography.Text>

      <Column
        data={histData}
        xField="label"
        yField="value"
        height={170}
        axis={{ y: { title: false } }}
        style={{ maxWidth: '100%' }}
      />

      <Typography.Text type="secondary" style={{ fontSize: 12 }}>实际真阳率（按标注数据）</Typography.Text>
      {calData.length > 0 ? (
        <Line
          data={calData}
          xField="label"
          yField="value"
          height={130}
          axis={{ y: { title: false, min: 0, max: 1 } }}
          point={{ size: 3 }}
          style={{ maxWidth: '100%' }}
        />
      ) : (
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          暂无标注数据（标记真阳/误报后才会出现校准曲线）
        </Typography.Text>
      )}
    </Space>
  );
}
