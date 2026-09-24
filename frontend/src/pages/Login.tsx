import { useState } from 'react';
import { Form, Input, Button, Card, Typography, App } from 'antd';
import { UserOutlined, LockOutlined } from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '../stores/auth.store';
import { errMsg } from '../api/http';

export default function Login() {
  const login = useAuthStore((s) => s.login);
  const navigate = useNavigate();
  const location = useLocation();
  const { message } = App.useApp();
  const [busy, setBusy] = useState(false);

  const onFinish = async (values: { username: string; password: string }) => {
    setBusy(true);
    try {
      await login(values.username, values.password);
      const from = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname || '/dashboard';
      navigate(from, { replace: true });
    } catch (e) {
      message.error(errMsg(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center' }}>
      <Card style={{ width: 380, boxShadow: '0 8px 24px rgba(16,24,40,0.10)' }}>
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <div style={{ fontSize: 36, lineHeight: 1 }}>🧠</div>
          <Typography.Title level={4} style={{ marginTop: 12, marginBottom: 4 }}>
            Soma
          </Typography.Title>
          <Typography.Text type="secondary">安全运营工作台 · 登录</Typography.Text>
        </div>
        <Form onFinish={onFinish} layout="vertical" size="large">
          <Form.Item name="username" rules={[{ required: true, message: '请输入用户名' }]}>
            <Input prefix={<UserOutlined />} placeholder="用户名" autoFocus autoComplete="username" />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: '请输入密码' }]}>
            <Input.Password prefix={<LockOutlined />} placeholder="密码" autoComplete="current-password" />
          </Form.Item>
          <Button type="primary" htmlType="submit" block loading={busy}>
            登录
          </Button>
        </Form>
      </Card>
    </div>
  );
}
