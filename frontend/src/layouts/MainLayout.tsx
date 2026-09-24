import { useState } from 'react';
import {
  Layout, Menu, Dropdown, Space, Badge, Button, Modal, Form, Input, App, Segmented, Tooltip,
} from 'antd';
import {
  DashboardOutlined, ApartmentOutlined, OrderedListOutlined, RadarChartOutlined,
  SafetyCertificateOutlined, SettingOutlined, TeamOutlined, LogoutOutlined,
  SunOutlined, MoonOutlined, BookOutlined, KeyOutlined,
} from '@ant-design/icons';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useAuthStore } from '../stores/auth.store';
import { useUiStore } from '../stores/ui.store';
import { useTerms } from '../hooks/useTerms';
import { http, errMsg } from '../api/http';
import { authApi } from '../api/auth';

const { Header, Sider, Content } = Layout;

interface Health {
  db: { cases: number; alerts: number };
  syslog: { listening: boolean; last_ingest?: number };
  knob: string;
  mode: string;
}

export default function MainLayout() {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const { message } = App.useApp();
  const { user, logout } = useAuthStore();
  const { darkMode, toggleDark, termMode, setTermMode } = useUiStore();
  const { t } = useTerms();
  const [collapsed, setCollapsed] = useState(false);
  const [pwdOpen, setPwdOpen] = useState(false);
  const [form] = Form.useForm();

  const { data: health } = useQuery<Health>({
    queryKey: ['health'],
    queryFn: async () => (await http.get('/health')).data,
    refetchInterval: 15000,
  });

  const menuItems = [
    { key: '/dashboard', icon: <DashboardOutlined />, label: t('dashboard') },
    { key: '/hippocampus', icon: <ApartmentOutlined />, label: t('hippocampus') },
    { key: '/triage', icon: <OrderedListOutlined />, label: t('triage') },
    { key: '/thalamus', icon: <RadarChartOutlined />, label: t('thalamus') },
    { key: '/immune', icon: <SafetyCertificateOutlined />, label: t('immune') },
    { key: '/settings', icon: <SettingOutlined />, label: t('settings') },
    { key: '/users', icon: <TeamOutlined />, label: '用户' },
  ];

  let selected = '/' + (pathname.split('/')[1] || 'dashboard');
  if (pathname.startsWith('/cases/')) selected = '/triage';

  const changePassword = async (values: { old_password: string; new_password: string }) => {
    try {
      await authApi.changePassword(values.old_password, values.new_password);
      message.success('密码已修改');
      setPwdOpen(false);
      form.resetFields();
    } catch (e) {
      message.error(errMsg(e));
    }
  };

  const userMenu = {
    items: [
      { key: 'pwd', icon: <KeyOutlined />, label: '修改密码' },
      { type: 'divider' as const },
      { key: 'logout', icon: <LogoutOutlined />, label: '退出登录' },
    ],
    onClick: ({ key }: { key: string }) => {
      if (key === 'logout') {
        logout();
        navigate('/login');
      } else if (key === 'pwd') {
        setPwdOpen(true);
      }
    },
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider collapsible collapsed={collapsed} onCollapse={setCollapsed} width={200}>
        <div
          style={{
            height: 56, display: 'grid', placeItems: 'center', color: '#fff',
            fontWeight: 700, fontSize: collapsed ? 16 : 15, whiteSpace: 'nowrap', overflow: 'hidden',
          }}
        >
          {collapsed ? '🧠' : '🧠 Soma'}
        </div>
        <Menu
          theme="dark" mode="inline" selectedKeys={[selected]} items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header
          style={{
            padding: '0 20px', display: 'flex', alignItems: 'center', gap: 20,
            borderBottom: '1px solid rgba(5,5,5,0.06)', background: 'transparent',
          }}
        >
          <Space size={18}>
            <Badge
              status={health?.syslog.listening ? 'success' : 'default'}
              text={<span style={{ fontSize: 13 }}>{health?.syslog.listening ? '值守中' : '未监听'}</span>}
            />
            <span style={{ fontSize: 13 }}>
              {t('knob')} <b>{health?.knob ?? '…'}</b>
            </span>
            <span style={{ fontSize: 13 }}>
              案件 <b>{health?.db.cases ?? 0}</b>
            </span>
          </Space>

          <div style={{ flex: 1 }} />

          <Segmented
            value={termMode}
            onChange={(v) => setTermMode(v as 'bio' | 'sec')}
            options={[
              { label: '生物术语', value: 'bio' },
              { label: '安全术语', value: 'sec' },
            ]}
          />

          <Tooltip title={darkMode ? '切到浅色' : '切到暗色'}>
            <Button
              type="text"
              icon={darkMode ? <SunOutlined /> : <MoonOutlined />}
              onClick={toggleDark}
            />
          </Tooltip>

          <Tooltip title="用户手册">
            <Button type="text" icon={<BookOutlined />} onClick={() => window.open('/manual.html', '_blank', 'noopener')} />
          </Tooltip>

          <Dropdown menu={userMenu}>
            <Button type="text">
              <Space size={6}>
                <Badge color={user?.role === 'admin' ? 'blue' : 'default'} />
                {user?.username}
                {user?.role === 'admin' ? ' · 管理员' : ''}
              </Space>
            </Button>
          </Dropdown>
        </Header>
        <Content style={{ padding: 24 }}>
          <Outlet />
        </Content>
      </Layout>

      <Modal
        title="修改密码" open={pwdOpen} onCancel={() => setPwdOpen(false)} onOk={() => form.submit()}
        okText="确认" cancelText="取消"
      >
        <Form form={form} layout="vertical" onFinish={changePassword} style={{ marginTop: 12 }}>
          <Form.Item name="old_password" label="当前密码" rules={[{ required: true, message: '请输入当前密码' }]}>
            <Input.Password autoComplete="current-password" />
          </Form.Item>
          <Form.Item name="new_password" label="新密码" rules={[{ required: true, message: '请输入新密码' }, { min: 6, message: '至少 6 位' }]}>
            <Input.Password autoComplete="new-password" />
          </Form.Item>
        </Form>
      </Modal>
    </Layout>
  );
}
