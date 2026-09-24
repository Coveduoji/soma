import axios from 'axios';

const BASE = '/api';

export const http = axios.create({ baseURL: BASE });

// 请求拦截：统一挂 Bearer token。
http.interceptors.request.use((config) => {
  const token = localStorage.getItem('soma_jwt');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// 401 统一处理：清 token 并通知上层（退回登录页）。
let unauthorizedHandler: (() => void) | null = null;
export function setUnauthorizedHandler(fn: (() => void) | null) {
  unauthorizedHandler = fn;
}

http.interceptors.response.use(
  (r) => r,
  (error) => {
    if (error?.response?.status === 401) {
      localStorage.removeItem('soma_jwt');
      unauthorizedHandler?.();
    }
    return Promise.reject(error);
  },
);

// 从 axios error 提取后端 detail 文案，供 antd message 显示。
export function errMsg(e: unknown): string {
  if (axios.isAxiosError(e)) {
    const d = e.response?.data;
    if (d && typeof d === 'object' && typeof (d as { detail?: unknown }).detail === 'string') {
      return (d as { detail: string }).detail;
    }
    if (e.response?.status) return `${e.response.status} ${e.response.statusText}`;
    return e.message;
  }
  return String(e);
}

// 触发浏览器下载一个 blob（报告导出等）。
export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// 从 Content-Disposition 头解析文件名（后端报告导出用）。
export function filenameFromDisposition(disp: string): string | null {
  const m = disp.match(/filename="?([^";]+)"?/);
  return m ? m[1] : null;
}
