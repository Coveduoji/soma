import type { AuthUser } from '../types/models';

// 权限键 → 中文说明（与后端 auth.PERMISSIONS 对应）
export const PERMISSIONS: Record<string, string> = {
  triage: '分诊（标记/放回/改案件/外发/免疫规则/主动研判）',
  config: '配置（旋钮/模型/检测/接入/Webhook 等）',
  maintenance: '维护（清库/夜间巩固）',
  users: '用户管理',
};

// admin 隐式全权限；user 按 permissions 列表判断
export function hasPerm(user: AuthUser | null, perm: string): boolean {
  if (!user) return false;
  return user.role === 'admin' || (user.permissions ?? []).includes(perm);
}
