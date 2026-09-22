import { http, downloadBlob, filenameFromDisposition } from './http';
import type { DashboardData, TrendData, TrendBucket, RawAlert, AuditEntry, HippocampusData, Report } from '../types/models';

export const dashboardApi = {
  dashboard: async () => (await http.get<DashboardData>('/dashboard')).data,
  trend: async (start: number, end: number) =>
    (await http.get<{ start: number; end: number; buckets: TrendBucket[] }>(`/trend?start=${start}&end=${end}`)).data,
  calibration: async (source = '') =>
    (await http.get<{
      buckets: { label: string; count: number; tp: number; fp: number; tp_rate: number | null }[];
      thresholds: { suppress_below: number; escalate_above: number };
      sources: string[];
    }>(`/calibration${source ? `?source=${encodeURIComponent(source)}` : ''}`)).data,
  deviceTraffic: async (start: number, end: number) =>
    (await http.get<{ start: number; end: number; sources: string[]; items: { t: number; source: string; count: number }[] }>(
      `/device-traffic?start=${start}&end=${end}`
    )).data,
  deviceClassification: async (source: string, start: number, end: number) =>
    (await http.get<{ source: string; items: { type: string; count: number }[] }>(
      `/device-classification?start=${start}&end=${end}${source ? `&source=${encodeURIComponent(source)}` : ''}`
    )).data,
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
  deadLetter: async () => (await http.get<{ count: number; items: any[] }>('/kafka/dead-letter')).data,
  replayDeadLetter: async () =>
    (await http.post<{ replayed: number; failed: number; remaining: number }>('/kafka/dead-letter/replay')).data,
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
