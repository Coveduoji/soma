import { http, downloadBlob, filenameFromDisposition } from './http';
import type { Case, CaseDetail, GraphData, Report } from '../types/models';

export const casesApi = {
  listCases: async (query = '') =>
    (await http.get<{ items: Case[]; total: number }>(`/cases${query ? `?${query}` : ''}`)).data,
  getCase: async (id: number) => (await http.get<CaseDetail>(`/cases/${id}`)).data,
  caseHippocampus: async (id: number) => (await http.get<GraphData>(`/cases/${id}/hippocampus`)).data,
  patchCase: async (id: number, body: object) => (await http.patch(`/cases/${id}`, body)).data,
  falsePositive: async (id: number, reason = '') =>
    (await http.post<{ learned: [string, string][] }>(`/cases/${id}/false-positive`, { reason })).data,
  truePositive: async (id: number, reason = '') =>
    (await http.post<{ learned: [string, string][] }>(`/cases/${id}/true-positive`, { reason })).data,
  bulkFalsePositive: async (caseIds: number[], reason = '') =>
    (await http.post<{ learned: [string, string][] }>(`/cases/bulk-false-positive`, { case_ids: caseIds, reason })).data,
  alertDisposition: async (alertId: number, verdict: string) =>
    (await http.post(`/alerts/${alertId}/disposition`, { verdict })).data,
  entityCases: async (type: string, value: string) =>
    (await http.get<Case[]>(`/entities/cases?type=${encodeURIComponent(type)}&value=${encodeURIComponent(value)}`)).data,
  pushCase: async (id: number) =>
    (await http.post<{ case_id: number; results: { name: string; url: string; ok: boolean }[] }>(`/cases/${id}/push`)).data,
  analyzeCase: async (id: number) =>
    (await http.post<Report>(`/cases/${id}/analyze`)).data,
  exportCase: async (id: number) => {
    const r = await http.get(`/cases/${id}/export`, { responseType: 'blob' });
    downloadBlob(r.data as Blob, filenameFromDisposition(r.headers['content-disposition'] || '') || `case_${id}.md`);
  },
};
