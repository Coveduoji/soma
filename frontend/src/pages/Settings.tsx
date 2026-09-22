import { useState } from 'react';
import { Card, Space, Typography, Button, Segmented, Descriptions, App, Tag } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { configApi } from '../api/config';
import { dashboardApi } from '../api/dashboard';
import { useTerms } from '../hooks/useTerms';
import { useUiStore } from '../stores/ui.store';
import { useHasPerm } from '../hooks/useHasPerm';
import { http, errMsg } from '../api/http';
import AdvancedSettings from './AdvancedSettings';

export default function Settings() {
  const { t } = useTerms();
  const { termMode, setTermMode } = useUiStore();
  const canConfig = useHasPerm('config');
  const canMaintain = useHasPerm('maintenance');
  const { message, modal } = App.useApp();
  const qc = useQueryClient();
  const [showAdvanced, setShowAdvanced] = useState(false);

  const { data: presets } = useQuery({ queryKey: ['presets'], queryFn: configApi.presets, enabled: canConfig });
  const { data: mode } = useQuery({ queryKey: ['mode'], queryFn: configApi.mode, enabled: canConfig });
  const { data: info } = useQuery({ queryKey: ['info'], queryFn: configApi.info });
  const { data: healthInfo } = useQuery({
    queryKey: ['health'],
    queryFn: async () => (await http.get('/health')).data,
    enabled: canMaintain,
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['health'] });
    qc.invalidateQueries({ queryKey: ['dashboard'] });
  };

  const setKnob = async (knob: string) => {
    try {
      await dashboardApi.setKnob(knob);
      message.success(`${t('knob')}已切到「${knob}」`);
      invalidate();
    } catch (e) {
      message.error(errMsg(e));
    }
  };

  const setMode = async (m: string) => {
    try {
      await configApi.setMode(m);
      message.success(m === 'mock' ? '已切到 Mock 模式（零成本）' : m === 'real' ? '已切到真实模型' : '已切到自动模式');
      invalidate();
    } catch (e) {
      message.error(errMsg(e));
    }
  };

  const resetDb = () => {
    modal.confirm({
      title: '确定清空所有告警 / 案件 / 报告？此操作不可撤销。',
      onOk: async () => {
        await configApi.reset();
        message.success('已清空数据库');
        invalidate();
      },
    });
  };

  const runConsolidate = async () => {
    try {
      const r = await configApi.consolidate();
      message.success(r.memory ? `已巩固记忆：${r.memory.slice(0, 40)}…` : '巩固完成（无数据）');
    } catch (e) {
      message.error(errMsg(e));
    }
  };

  if (showAdvanced && canConfig) {
    return <AdvancedSettings onBack={() => setShowAdvanced(false)} />;
  }

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Typography.Title level={4} style={{ margin: 0 }}>{t('settings')}</Typography.Title>
        {canConfig && (
          <Button onClick={() => setShowAdvanced(true)}>高级设置 →</Button>
        )}
      </Space>

      <Space orientation="vertical" size={16} style={{ width: '100%' }}>
        {canConfig && (
          <Card title={t('knob')} size="small">
            <Space wrap>
              {Object.entries(presets ?? {}).map(([name, p]) => (
                <Button
                  key={name}
                  type={name === healthInfo?.knob ? 'primary' : 'default'}
                  onClick={() => setKnob(name)}
                >
                  {name}（抑制 {p.suppress_below} · 顶出 {p.escalate_above} · 预算 {p.budget}）
                </Button>
              ))}
            </Space>
          </Card>
        )}

        {canConfig && (
          <Card title="模型模式" size="small">
            <Typography.Paragraph type="secondary">
              切换杏仁核/前额叶用 mock 还是真实模型，免重启立即生效。
            </Typography.Paragraph>
            <Segmented
              value={mode?.mode}
              onChange={(v) => setMode(v as string)}
              options={[
                { label: '自动', value: 'auto' },
                { label: '真实（DeepSeek）', value: 'real' },
                { label: 'Mock（零成本）', value: 'mock' },
              ]}
            />
          </Card>
        )}

        {(canConfig || canMaintain) && (
          <Card title="数据接入" size="small">
            {info && (
              <Typography.Paragraph type="secondary" style={{ marginBottom: 12 }}>
                syslog 接收：UDP/TCP <Tag>{info.syslog.bind}:{info.syslog.port}</Tag>
                杏仁核（初筛）模型：<Tag>{info.model}</Tag> · 前额叶（深度分析）模型：<Tag>{info.deep_model}</Tag>
              </Typography.Paragraph>
            )}
            {canMaintain && (
              <Typography.Paragraph type="secondary" style={{ marginTop: 8, marginBottom: 0 }}>
                也可以把 rsyslog / 网络设备转发到上面的 syslog 端口，实时接入。
              </Typography.Paragraph>
            )}
          </Card>
        )}

        {canMaintain && (
          <Card title="健康状态" size="small">
            {healthInfo && (
              <Descriptions column={1} size="small" style={{ marginBottom: 12 }}>
                <Descriptions.Item label="数据库">{healthInfo.db?.alerts} 告警 / {healthInfo.db?.cases} 案件</Descriptions.Item>
                <Descriptions.Item label="syslog">{healthInfo.syslog?.listening ? '监听中' : '未启动'}</Descriptions.Item>
                <Descriptions.Item label={t('knob')}>{healthInfo.knob}</Descriptions.Item>
                <Descriptions.Item label="模型">{healthInfo.mode ?? '…'}</Descriptions.Item>
              </Descriptions>
            )}
            <Space>
              <Button icon={<ReloadOutlined />} onClick={invalidate}>刷新</Button>
              <Button onClick={runConsolidate}>立即夜间巩固</Button>
              <Button danger onClick={resetDb}>清空数据库</Button>
            </Space>
          </Card>
        )}

        <Card title="界面术语" size="small">
          <Segmented
            value={termMode}
            onChange={(v) => setTermMode(v as 'bio' | 'sec')}
            options={[
              { label: '生物术语（丘脑 · 海马体 · 免疫 · 神经调质）', value: 'bio' },
              { label: '安全术语（原始告警 · 关联分析 · 规则库 · 风险等级）', value: 'sec' },
            ]}
          />
        </Card>
      </Space>
    </div>
  );
}
