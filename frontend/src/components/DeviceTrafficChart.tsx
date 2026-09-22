import { Line } from '@ant-design/plots';
import { Empty } from 'antd';
import dayjs from 'dayjs';

interface Item { t: number; source: string; count: number; }

export default function DeviceTrafficChart({ items }: { items: Item[] }) {
  if (!items || items.length === 0) return <Empty description="暂无设备流量数据" />;

  const data = items.map((i) => ({
    time: dayjs(i.t * 1000).format('MM-DD HH:mm'),
    series: i.source,
    value: i.count,
  }));

  const config = {
    data,
    xField: 'time',
    yField: 'value',
    colorField: 'series',
    height: 260,
    axis: { y: { title: false } },
    legend: { color: { position: 'top' } },
  };

  return <Line {...config} />;
}
