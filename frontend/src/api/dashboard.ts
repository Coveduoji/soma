import { http, downloadBlob, filenameFromDisposition } from './http';
import type { DashboardData, TrendData, RawAlert, AuditEntry, HippocampusData, Report } from '../types/models';

export const dashboardApi = {
  dashboard: async () => (await http.get<DashboardData>('/dashboard')).data,
  trend: async (range = '24h') => (await http.get<TrendData>(`/trend?range=${range}`)).data,
  setKnob: async (knob: string) => (await http.put('/knob', { knob })).data,
  toleranceRemove: async (signature: string) => (await http.post('/tolerance/remove', { signature })).data,
  toleranceClear: async () => (await http.post('/tolerance/clear')).data,
  innateRemove: async (signature: string) => (await http.post('/innate/remove', { signature })).data,
  innateClear: async () => (await http.post('/innate/clear')).data,
  suppressed: async () => (await http.get<any[]>('/suppressed')).data,
  restore: async (id: number) =>
    (await http.post<{ case_id: number; correlation_uid: string }>(`/suppressed/${id}/restore`)).data,
  analyzeAlert: async (alertId: number) =>
    (await http.post<Report>(`/alerts/${alertId}/analyze`)).data,
  thalamus: async (params: Record<string, string>) =>
    (await http.get<{ items: RawAlert[]; total: number; sources: string[] }>(`/thalamus?${new URLSearchParams(params).toString()}`)).data,
  audit: async () => (await http.get<{ items: AuditEntry[] }>('/audit')).data,
  hippocampus: async () => (await http.get<HippocampusData>('/hippocampus')).data,
  hippocampusEvents: async (params: Record<string, string>) =>
    (await http.get<{ items: any[]; total: number; sources: string[] }>(`/hippocampus/events?${new URLSearchParams(params).toString()}`)).data,
  exportReport: async (body: object) => {
    const r = await http.post('/report/export', body, { responseType: 'blob' });
    downloadBlob(r.data as Blob, filenameFromDisposition(r.headers['content-disposition'] || '') || 'report');
  },
};
