import { http } from './http';
import type {
  FreqConfig, GatingConfig, ModelConfig, DetectionConfig, IngestConfig,
  SourcesConfig, SourceStatus, ParsersConfig, SourceParserConfig, WebhookConfig,
  AssetItem,
} from '../types/models';

export const configApi = {
  presets: async () =>
    (await http.get<Record<string, { suppress_below: number; escalate_above: number; budget: number }>>('/presets')).data,
  updatePreset: async (name: string, body: object) => (await http.put(`/presets/${name}`, body)).data,
  freq: async () => (await http.get<FreqConfig>('/freq')).data,
  setFreq: async (body: object) => (await http.put<FreqConfig>('/freq', body)).data,
  gating: async () => (await http.get<GatingConfig>('/gating')).data,
  setGating: async (body: object) => (await http.put<GatingConfig>('/gating', body)).data,
  mode: async () => (await http.get<{ mode: string }>('/mode')).data,
  setMode: async (mode: string) => (await http.put<{ mode: string }>('/mode', { mode })).data,
  model: async () => (await http.get<ModelConfig>('/model')).data,
  setModel: async (body: object) => (await http.put<ModelConfig>('/model', body)).data,
  testModel: async (body: object) =>
    (await http.post<{ ok: boolean; error: string; elapsed: number }>('/model/test', body)).data,
  detection: async () => (await http.get<DetectionConfig>('/detection')).data,
  setDetection: async (body: object) => (await http.put<DetectionConfig>('/detection', body)).data,
  ingest: async () => (await http.get<IngestConfig>('/ingest')).data,
  setIngest: async (body: object) => (await http.put<IngestConfig>('/ingest', body)).data,
  sources: async () => (await http.get<SourcesConfig>('/sources')).data,
  setSources: async (body: object) => (await http.put<SourcesConfig>('/sources', body)).data,
  sourceStatus: async () => (await http.get<{ items: SourceStatus[] }>('/sources/status')).data,
  assets: async () => (await http.get<{ items: AssetItem[] }>('/assets')).data,
  setAssets: async (items: AssetItem[]) => (await http.put<{ items: AssetItem[] }>('/assets', { items })).data,
  parsers: async () => (await http.get<ParsersConfig>('/parsers')).data,
  setParsers: async (body: object) => (await http.put<ParsersConfig>('/parsers', body)).data,
  generateParsers: async (body: object) =>
    (await http.post<{ config: SourceParserConfig }>('/parsers/generate', body)).data,
  memory: async () => (await http.get<{ items: any[] }>('/memory')).data,
  deleteMemory: async (index: number) => (await http.delete<{ items: any[] }>(`/memory/${index}`)).data,
  clearMemory: async () => (await http.delete<{ items: any[] }>('/memory')).data,
  feedback: async () => (await http.get<{ items: any[] }>('/feedback')).data,
  deleteFeedback: async (index: number) => (await http.delete<{ items: any[] }>(`/feedback/${index}`)).data,
  clearFeedback: async () => (await http.delete<{ items: any[] }>('/feedback')).data,
  webhooks: async () => (await http.get<{ items: WebhookConfig[] }>('/webhooks')).data,
  addWebhook: async (body: object) => (await http.post<{ items: WebhookConfig[] }>('/webhooks', body)).data,
  updateWebhook: async (index: number, body: object) =>
    (await http.put<{ items: WebhookConfig[] }>(`/webhooks/${index}`, body)).data,
  deleteWebhook: async (index: number) => (await http.delete<{ items: WebhookConfig[] }>(`/webhooks/${index}`)).data,
  testWebhook: async (index: number) => (await http.post<{ ok: boolean }>(`/webhooks/${index}/test`)).data,
  reset: async () => (await http.post<{ status: string }>('/reset')).data,
  consolidate: async () => (await http.post<{ status: string; memory: string | null }>('/consolidate')).data,
  info: async () =>
    (await http.get<{ syslog: { bind: string; port: number }; model: string; deep_model: string }>('/info')).data,
  upload: async (file: File) => {
    const fd = new FormData();
    fd.append('file', file);
    return (await http.post<{ ingested: number }>('/ingest/upload', fd)).data;
  },
};
