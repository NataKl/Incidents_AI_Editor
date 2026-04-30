export const API_BASE = "/api";

export async function apiJson<T>(
  path: string,
  init?: RequestInit,
): Promise<{ ok: boolean; status: number; data: T }> {
  const r = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.headers as Record<string, string>),
    },
    cache: init?.cache ?? "no-store",
  });
  const text = await r.text();
  let data: T = undefined as T;
  if (text) {
    try {
      data = JSON.parse(text) as T;
    } catch {
      data = text as T;
    }
  }
  return { ok: r.ok, status: r.status, data };
}

export type EventRow = {
  event_id: string;
  id?: string;
  created_at: string;
  ts: string | null;
  service: string;
  level: string;
  message: string;
};

export type DashboardSnapshot = {
  events: {
    total: number;
    linked_to_incident: number;
    unlinked: number;
  };
  incidents: {
    total: number;
    by_priority: Record<string, number>;
    blocking: number;
    critical: number;
    urgent: number;
    medium: number;
    low: number;
  };
  incident_rows: Array<{
    incident_id: string;
    id?: string;
    created_at: string;
    title: string;
    priority: number;
    events: EventRow[];
    diagnosis_confidence?: "high" | "medium" | "low" | null;
    diagnosis_needs_review?: boolean | null;
  }>;
};

export type IncidentRow = {
  incident_id: string;
  created_at: string;
  title: string;
  priority: number;
  /** Последняя диагностика: поле confidence из сохранённого JSON, если диагностика была */
  diagnosis_confidence?: "high" | "medium" | "low" | null;
  /** Требование проверки (как тег «требует проверки» на экране диагностики); null если диагностики не было */
  diagnosis_needs_review?: boolean | null;
};

export type DiagnosisView = {
  root_cause_hypothesis: string;
  confidence: "high" | "medium" | "low";
  next_steps: string[];
  needs_review: boolean;
};

export type AuditRow = {
  id: string;
  created_at: string;
  action: string;
  status: string;
  error: string | null;
  duration_ms: number | null;
};
