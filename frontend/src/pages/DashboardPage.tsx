import { useCallback, useEffect, useState } from "react";
import {
  apiJson,
  type DashboardSnapshot,
  type EventRow,
} from "../api";
import { formatDateTimeDisplay, PRIORITY_OPTIONS, priorityHeatClass } from "../utils";

function StatCard({
  label,
  value,
  variant,
}: {
  label: string;
  value: number | string;
  variant: "neutral" | "total" | "linked" | "unlinked";
}) {
  return (
    <div className={`lead-stat-card lead-stat-card--${variant}`}>
      <span className="lead-stat-value">{value}</span>
      <span className="lead-stat-label">{label}</span>
    </div>
  );
}

function IncidentsPriorityGrid({ incidents }: { incidents: DashboardSnapshot["incidents"] }) {
  return (
    <div className="lead-incidents-equal-grid" role="list" aria-label="Инциденты и распределение по приоритету">
      <div className="lead-inc-cell lead-inc-cell--total" role="listitem">
        <span className="lead-inc-num">{incidents.total}</span>
        <span className="lead-inc-sub">Всего инцидентов</span>
      </div>
      {PRIORITY_OPTIONS.map((o) => {
        const cnt = incidents.by_priority[String(o.value)] ?? 0;
        return (
          <div
            key={o.value}
            className={`lead-inc-cell ${priorityHeatClass(o.value)}`}
            role="listitem"
            aria-label={`${o.label}: ${cnt}`}
          >
            <span className="lead-inc-prio-count">{cnt}</span>
            <span className="lead-inc-prio-label">{o.label}</span>
          </div>
        );
      })}
    </div>
  );
}

export function DashboardPage() {
  const [snap, setSnap] = useState<DashboardSnapshot | null>(null);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [openIds, setOpenIds] = useState<Set<string>>(new Set());

  const loadDashboard = useCallback(async () => {
    setLoadErr(null);
    const { ok, data } = await apiJson<DashboardSnapshot>(`/admin/dashboard`);
    if (ok && data && typeof data === "object" && "events" in data) {
      setSnap(data);
    } else {
      const msg =
        typeof data === "object" && data && "detail" in data
          ? JSON.stringify((data as { detail: unknown }).detail)
          : "Не удалось загрузить дашборд";
      setLoadErr(msg);
      setSnap(null);
    }
  }, []);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  const toggleRow = (id: string) => {
    setOpenIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <div className="grid-main dashboard-root dashboard-root--lead">
      <section className="card span-2 dashboard-hero">
        <div className="card-heading-row">
          <h2>Дашборд инцидентов и событий с ИИ-диагностикой</h2>
          <button type="button" className="btn btn-ghost lead-refresh-btn" onClick={() => void loadDashboard()}>
            Обновить
          </button>
        </div>
        <p className="section-intro lead-intro">
          Сводка по событиям и инцидентам. Важные инциденты показаны выше в списке; ниже — средний и низкий
          приоритет.
        </p>

        {loadErr && <p className="msg err">{loadErr}</p>}

        {snap && (
          <>
            <h3 className="dashboard-section-title">События</h3>
            <div className="lead-stat-grid lead-stat-grid--events lead-stat-grid--compact">
              <StatCard label="всего" value={snap.events.total} variant="total" />
              <StatCard
                label="связаны с инцидентом"
                value={snap.events.linked_to_incident}
                variant="linked"
              />
              <StatCard
                label="не связаны с инцидентом"
                value={snap.events.unlinked}
                variant="unlinked"
              />
            </div>

            <h3 className="dashboard-section-title">Инциденты</h3>
            <IncidentsPriorityGrid incidents={snap.incidents} />
          </>
        )}
      </section>

      <section className="card span-2 lead-table-section">
        <h2>Инциденты</h2>
        <p className="section-intro muted lead-table-hint">
          Блокирующие, критичные и срочные показываются выше списка. Нажмите ▶ чтобы открыть связанные события.
        </p>

        {!snap?.incident_rows.length && snap?.incidents.total === 0 && (
          <p className="muted">Инцидентов пока нет.</p>
        )}

        {snap != null && snap.incident_rows.length > 0 && (
          <div className="table-wrap table-wrap-lead">
            <table className="data dashboard-incidents-table lead-table">
              <thead>
                <tr>
                  <th className="th-narrow" />
                  <th className="th-prio-vis" aria-label="Приоритет" />
                  <th>Заголовок</th>
                  <th>Статус диагностики</th>
                  <th>Создан</th>
                  <th>Событий</th>
                  <th className="th-id">Инцидент</th>
                </tr>
              </thead>
              <tbody>
                {snap.incident_rows.map((row) => {
                  const expanded = openIds.has(row.incident_id);
                  return (
                    <IncidentRowBlock
                      key={row.incident_id}
                      row={row}
                      expanded={expanded}
                      onToggle={() => toggleRow(row.incident_id)}
                    />
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function IncidentRowBlock({
  row,
  expanded,
  onToggle,
}: {
  row: DashboardSnapshot["incident_rows"][number];
  expanded: boolean;
  onToggle: () => void;
}) {
  const n = row.events?.length ?? 0;
  const dc = row.diagnosis_confidence;
  const dn = row.diagnosis_needs_review;
  const noDiag = dc == null && (dn === null || dn === undefined);
  return (
    <>
      <tr className={expanded ? "dashboard-row-open lead-row" : "lead-row"}>
        <td className="cell-toggle">
          <button
            type="button"
            className="btn btn-ghost dashboard-toggle lead-toggle"
            aria-expanded={expanded}
            onClick={onToggle}
            title={expanded ? "Свернуть" : "Подробнее — события"}
          >
            {expanded ? "▼" : "▶"}
          </button>
        </td>
        <td className="cell-prio-heat">
          <span
            className={`lead-prio-bar ${priorityHeatClass(row.priority)}`}
            aria-label={`Приоритет ${row.priority}`}
          />
        </td>
        <td className="incidents-cell-desc" title={row.title}>
          <span className="incidents-desc-text">{row.title}</span>
        </td>
        <td className="lead-cell-diagnosis">
          {noDiag ? (
            <span className="muted">—</span>
          ) : (
            <>
              {dc ? (
                <span className="pill" title="Уверенность диагностики (из diagnoses)">
                  {dc}
                </span>
              ) : null}
              {dn === true ? (
                <span className="pill review">требует проверки</span>
              ) : null}
            </>
          )}
        </td>
        <td className="incidents-cell-time">
          <small title={row.created_at}>{formatDateTimeDisplay(row.created_at)}</small>
        </td>
        <td>
          <span className="pill lead-ev-count">{n}</span>
        </td>
        <td className="cell-id">
          <code className="inline">{row.incident_id}</code>
        </td>
      </tr>
      {expanded && (
        <tr className="dashboard-detail-row lead-detail-tr">
          <td colSpan={7}>
            <div className="dashboard-detail-inner lead-detail-inner">
              <p className="dashboard-detail-head">
                Связанные события <span className="muted">({n})</span>
              </p>
              {n === 0 ? (
                <p className="muted">Нет привязанных событий.</p>
              ) : (
                <div className="table-wrap">
                  <table className="data dashboard-events-nested lead-nested-table">
                    <thead>
                      <tr>
                        <th className="th-lev-vis" aria-label="Уровень" />
                        <th>Сервис</th>
                        <th>Сообщение</th>
                        <th>Время</th>
                        <th className="th-id">Событие</th>
                      </tr>
                    </thead>
                    <tbody>
                      {row.events.map((e: EventRow) => (
                        <tr key={e.event_id}>
                          <td className="cell-ev-lev">
                            <span
                              className={`lead-ev-dot lev-${e.level}`}
                              aria-label={e.level}
                              title=""
                            />
                          </td>
                          <td>{e.service}</td>
                          <td className="incidents-cell-desc">
                            <span className="incidents-desc-text">{e.message}</span>
                          </td>
                          <td>
                            <small>{formatDateTimeDisplay(e.created_at || e.ts)}</small>
                          </td>
                          <td className="cell-id">
                            <code className="inline">{e.event_id}</code>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
