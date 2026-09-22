import { useState } from 'react';
import { Modal, Form, Select, Radio, DatePicker, App } from 'antd';
import dayjs from 'dayjs';
import { dashboardApi } from '../../api/dashboard';
import { errMsg } from '../../api/http';

const FORMATS = [
  { value: 'docx', label: 'Word (.docx)' },
  { value: 'md', label: 'Markdown (.md)' },
  { value: 'html', label: 'HTML (.html)' },
];

const VERDICTS = ['True Positive', 'Suspicious', 'False Positive', 'Benign', 'Insufficient Data'];
const STATUSES = ['New', 'In Progress', 'On Hold', 'Resolved', 'Closed'];

export default function ExportReport({ open, onClose, sources }: {
  open: boolean;
  onClose: () => void;
  sources?: string[];
}) {
  const { message } = App.useApp();
  const [form] = Form.useForm();
  const [busy, setBusy] = useState(false);

  const doExport = async () => {
    const v = form.getFieldsValue();
    setBusy(true);
    const body: Record<string, string> = { format: v.format || 'html' };
    if (v.range && v.range[0] && v.range[1]) {
      body.start = v.range[0].format('YYYY-MM-DDTHH:mm');
      body.end = v.range[1].format('YYYY-MM-DDTHH:mm');
    }
    if (v.source) body.source = v.source;
    if (v.verdict) body.verdict = v.verdict;
    if (v.status) body.status = v.status;
    try {
      await dashboardApi.exportReport(body);
      message.success('报告已导出');
      onClose();
    } catch (e) {
      message.error('导出失败：' + errMsg(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal title="导出报告" open={open} onCancel={onClose} onOk={doExport} confirmLoading={busy} okText="导出">
      <Form form={form} layout="vertical" initialValues={{ format: 'html' }} style={{ marginTop: 8 }}>
        <Form.Item name="range" label="时间范围（留空 = 全部时间）">
          <DatePicker.RangePicker
            showTime
            style={{ width: '100%' }}
            presets={[
              { label: '近24小时', value: [dayjs().subtract(24, 'hour'), dayjs()] },
              { label: '近7天', value: [dayjs().subtract(7, 'day'), dayjs()] },
              { label: '近30天', value: [dayjs().subtract(30, 'day'), dayjs()] },
            ]}
          />
        </Form.Item>
        <Form.Item name="source" label="来源">
          <Select allowClear placeholder="全部" options={(sources ?? []).map((s) => ({ value: s, label: s }))} />
        </Form.Item>
        <Form.Item name="verdict" label="定性">
          <Select allowClear placeholder="全部" options={VERDICTS.map((v) => ({ value: v, label: v }))} />
        </Form.Item>
        <Form.Item name="status" label="状态">
          <Select allowClear placeholder="全部" options={STATUSES.map((v) => ({ value: v, label: v }))} />
        </Form.Item>
        <Form.Item name="format" label="格式">
          <Radio.Group options={FORMATS} optionType="button" />
        </Form.Item>
      </Form>
    </Modal>
  );
}
