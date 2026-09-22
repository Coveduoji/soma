export interface Entity {
  type: string;
  value: string;
}

export interface AuthUser {
  id: number;
  username: string;
  role: string;
  permissions: string[];
  created_at: string;
}

export interface Case {
  id: number;
  correlation_uid: string;
  title: string;
  strength: number;
  status: string;
  verdict: string;
  severity: string;
  risk?: number;
  risk_incomplete?: boolean;
  entities: Entity[];
}

export interface Alert {
  id: number;
  time: string;
  source: string;
  asset: string;
  type: string;
  raw: string;
  confidence: number;
  reason: string;
  innate: number;
  verdict?: string;
  artifacts: Entity[];
}

export interface Evidence {
  fact: string;
  conclusion: string;
}

export interface Ioc {
  value: string;
  context: string;
}

export interface Report {
  verdict: string;
  confidence: string;
  digest: string;
  evidence: Evidence[];
  attack_chain: { phase: string; description: string }[];
  iocs: Ioc[];
  unknowns: string[];
  remediations: string[];
}

export interface CaseDetail {
  case: Case;
  alerts: Alert[];
  report: Report | null;
}

export interface GraphData {
  nodes: { id: number; type: string; value: string }[];
  edges: [number, number][];
}

export interface DashboardData {
  counts: { alerts: number; surfaced: number; suppressed: number; artifacts: number; cases: number; reports: number; attack_chains: number; audit: number };
  knob: { name: string; suppress_below: number; escalate_above: number; budget: number };
  presets: Record<string, { suppress_below: number; escalate_above: number; budget: number }>;
  tolerance: string[];
  innate: string[];
}

export interface TrendBucket { t: number; total: number; surfaced: number; }
export interface TrendData { range: string; buckets: TrendBucket[]; }

export interface HippocampusNode {
  id: number;
  type: string;
  value: string;
  cases: string[];
  degree: number;
}

export interface HippocampusEdge {
  source: number;
  target: number;
  cases: string[];
}

export interface HippocampusData {
  nodes: HippocampusNode[];
  edges: HippocampusEdge[];
}

export interface FreqConfig {
  window: number;
  threshold: number;
  demote: number;
}

export interface GatingConfig {
  single_signal_floor: number;
  budget_window: number;
}

export interface RawAlert {
  id: number;
  case_id: number | null;
  time: string;
  source: string;
  asset: string;
  type: string;
  raw: string;
  confidence: number | null;
  reason: string;
  innate: number;
  suppressed: number;
  why: string;
  verdict: string;
  case_uid: string | null;
  created_at: string;
}

export interface AuditEntry {
  id: number;
  action: string;
  entity: string;
  changes: string;
  created_at: string;
}

export interface ModelConfig {
  api_key: string;
  base_url: string;
  model: string;
  deep_api_key: string;
  deep_base_url: string;
  deep_model: string;
  temperature: number;
  timeout: number;
}

export interface DetectionConfig {
  chain_bonus: number;
  chain_cap: number;
  grew: number;
  rag_limit: number;
  innate_conf: number;
  restore_conf: number;
  tolerance_ttl_days: number;
  mock_indicators: [string, number][];
  mock_no_hit: number;
  mock_base: number;
  mock_ceiling: number;
  mock_cutoff: number;
}

export interface IngestConfig {
  syslog_bind: string;
  syslog_port: number;
  consolidate_interval: number;
  api_token: string;
  retention_alert_days: number;
  retention_case_days: number;
}

export interface SourcesConfig {
  facility: Record<string, string>;
  hostname: Record<string, string>;
  tag: Record<string, string>;
  ip: Record<string, string>;
}

export interface SourceStatus {
  source: string;
  count: number;
  surfaced: number;
  suppressed: number;
  last_seen_ts: number | null;
}

export interface ParserRule {
  match: string;
  type: string;
  delimiter?: string;
  field_split?: string;
  value_split?: string;
  fields?: string[];
  enabled?: boolean;
  map: {
    time?: string;
    type?: string;
    asset?: string;
    entities?: [string, string][];
    severity?: string;
    severity_map?: Record<string, string>;
    attack_result?: string;
    attack_result_map?: Record<string, string>;
  };
}

export interface SourceParserConfig {
  strip_syslog?: boolean;
  parsers: ParserRule[];
}

export interface ParsersConfig {
  [source: string]: SourceParserConfig;
}

export interface WebhookConfig {
  name: string;
  url: string;
  token: string;
  trigger: string;
  enabled: boolean;
  fields: string[];
  headers: Record<string, string>;
  body: string;
}

export interface AssetItem {
  role: string;
  value: string;
  criticality: string;
}
