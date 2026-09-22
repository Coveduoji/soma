import { Pie } from '@ant-design/plots';
import { Empty } from 'antd';

interface Item { type: string; count: number; }

export default function DeviceClassChart({ items }: { items: Item[] }) {
  if (!items || items.length === 0) return <Empty description="暂无告警分类数据" />;

  const data = items.map((i) => ({ type: i.type, value: i.count }));

  const config = {
    data,
    angleField: 'value',
    colorField: 'type',
    innerRadius: 0.6,
    height: 260,
    legend: { color: { position: 'right' } },
  };

  return <Pie {...config} />;
}
