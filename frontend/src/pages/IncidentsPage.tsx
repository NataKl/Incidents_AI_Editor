import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiJson, type DiagnosisView, type EventRow, type IncidentRow } from "../api";
import { useAppShared } from "../AppContext";
import { formatDateTimeDisplay, levelClass, PRIORITY_OPTIONS, priorityLabel } from "../utils";

export function IncidentsPage() {
  const navigate = useNavigate();
  const {
    setDiagnosis,
    setDiagnosisIncidentId,
    incidentEventIdsDraft,
    setIncidentEventIdsDraft,
  } = useAppShared();

  const [incidents, setIncidents] = useState<IncidentRow[]>([]);
  const [incTitle, setIncTitle] = useState("");
  const [incEventIds, setIncEventIds] = useState("");
  const [incPriority, setIncPriority] = useState(3);
  const [incFormMsg, setIncFormMsg] = useState<{ t: "ok" | "err"; text: string } | null>(null);
  const [openDetail, setOpenDetail] = useState<{
    title: string;
    created_at: string;
    incident_id: string;
    priority: number;
    events: EventRow[];
  } | null>(null);
  const [diagRunMsg, setDiagRunMsg] = useState<{ t: "ok" | "err"; text: string } | null>(null);
  const incidentsListRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (incidentEventIdsDraft) {
      setIncEventIds(incidentEventIdsDraft);
      setIncidentEventIdsDraft("");
    }
  }, [incidentEventIdsDraft, setIncidentEventIdsDraft]);

  const loadIncidents = useCallback(async () => {
    const { ok, data } = await apiJson<IncidentRow[]>(`/incidents`);
    if (ok && Array.isArray(data)) setIncidents(data);
  }, []);

  useEffect(() => {
    void loadIncidents();
  }, [loadIncidents]);

  const fetchAndOpenIncident = useCallback(async (id: string) => {
    const { ok, data } = await apiJson<{
      title: string;
      created_at: string;
      incident_id: string;
      priority: number;
      events: EventRow[];
    }>(`/incidents/${encodeURIComponent(id)}`);
    if (ok && data && typeof data === "object" && "title" in data) {
      setOpenDetail(data);
      setDiagRunMsg(null);
    }
  }, []);

  const toggleIncidentRow = useCallback(
    (id: string) => {
      if (openDetail?.incident_id === id) {
        setOpenDetail(null);
        setDiagRunMsg(null);
        return;
      }
      void fetchAndOpenIncident(id);
    },
    [openDetail?.incident_id, fetchAndOpenIncident],
  );

  const onCreateIncident = async (e: React.FormEvent) => {
    e.preventDefault();
    setIncFormMsg(null);
    const event_ids = incEventIds
      .split(/[\s,]+/)
      .map((s) => s.trim())
      .filter(Boolean);
    const { ok, data } = await apiJson<{ incident_id: string }>(`/incidents`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: incTitle.trim(),
        event_ids,
        priority: incPriority,
      }),
    });
    if (ok && data && typeof data === "object" && "incident_id" in data) {
      setIncFormMsg({ t: "ok", text: `Инцидент ${data.incident_id}` });
      void loadIncidents();
      void fetchAndOpenIncident(data.incident_id);
    } else {
      const detail =
        typeof data === "object" && data && "detail" in data
          ? JSON.stringify((data as { detail: unknown }).detail)
          : String(data);
      setIncFormMsg({ t: "err", text: detail || "Ошибка" });
    }
  };

  const onRunDiagnose = async () => {
    setDiagRunMsg(null);
    if (!openDetail) {
      setDiagRunMsg({ t: "err", text: "Сначала откройте инцидент." });
      return;
    }
    const messages = openDetail.events.map((x) => x.message);
    const { ok, data } = await apiJson<DiagnosisView>(`/ai/diagnose`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: openDetail.title,
        messages,
        incident_id: openDetail.incident_id,
      }),
    });
    if (ok && data && typeof data === "object" && "confidence" in data) {
      setDiagnosis(data);
      setDiagnosisIncidentId(openDetail.incident_id);
      void loadIncidents();
      setDiagRunMsg({ t: "ok", text: "Готово — открыта страница диагностики." });
      navigate("/diagnosis");
    } else {
      const detail =
        typeof data === "object" && data && "detail" in data
          ? JSON.stringify((data as { detail: unknown }).detail)
          : String(data);
      setDiagRunMsg({ t: "err", text: detail || "Ошибка" });
    }
  };

  const backToIncidentsList = () => {
    setOpenDetail(null);
    setDiagRunMsg(null);
    queueMicrotask(() => {
      requestAnimationFrame(() => {
        incidentsListRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    });
  };

  return (
    <div className="grid-main incidents-layout">
      <section className="card incidents-toolbar-card">
        <div className="incidents-toolbar-head">
          <h2 className="incidents-toolbar-title">Новый инцидент</h2>
          <p className="section-intro incidents-toolbar-intro">
            <code className="inline">POST /api/incidents</code>
          </p>
        </div>
        <form onSubmit={onCreateIncident} className="incidents-toolbar-form">
          <label className="field incidents-toolbar-field incidents-toolbar-events">
            События (UUID через запятую)
            <input
              value={incEventIds}
              onChange={(e) => setIncEventIds(e.target.value)}
              required
              placeholder="uuid, uuid…"
              autoComplete="off"
            />
          </label>
          <label className="field incidents-toolbar-field incidents-toolbar-priority">
            Приоритет
            <select
              value={incPriority}
              onChange={(e) => setIncPriority(Number(e.target.value))}
            >
              {PRIORITY_OPTIONS.map(({ value, label }) => (
                <option key={value} value={value}>
                  {value} — {label}
                </option>
              ))}
            </select>
          </label>
          <label className="field incidents-toolbar-field incidents-toolbar-desc">
            Описание
            <input
              value={incTitle}
              onChange={(e) => setIncTitle(e.target.value)}
              required
              placeholder="Кратко: что наблюдаете"
              maxLength={500}
              autoComplete="off"
            />
          </label>
          <div className="incidents-toolbar-submit">
            <button type="submit" className="btn btn-primary">
              Создать инцидент
            </button>
          </div>
        </form>
        {incFormMsg && (
          <p className={`msg ${incFormMsg.t === "ok" ? "ok" : "err"}`}>{incFormMsg.text}</p>
        )}
      </section>

      <section ref={incidentsListRef} className="card incidents-layout-table incidents-table-card">
        <div className="card-heading-row">
          <h2>Последние инциденты</h2>
          <button type="button" className="btn btn-ghost" onClick={() => void loadIncidents()}>
            Обновить
          </button>
        </div>
        <div className="table-wrap table-wrap-fit">
          <table className="data incidents-table">
            <thead>
              <tr>
                <th>Приоритет</th>
                <th>Описание</th>
                <th>Статус диагностики</th>
                <th>Время создания инцидента</th>
                <th className="th-id">ID инцидента</th>
                <th className="th-actions" />
              </tr>
            </thead>
            <tbody>
              {incidents.map((r) => {
                const isOpen = openDetail?.incident_id === r.incident_id;
                const dc = r.diagnosis_confidence;
                const dn = r.diagnosis_needs_review;
                const noDiag = dc == null && (dn === null || dn === undefined);
                return (
                  <tr key={r.incident_id}>
                    <td>{priorityLabel(r.priority)}</td>
                    <td className="incidents-cell-desc" title={r.title}>
                      <span className="incidents-desc-text">{r.title}</span>
                    </td>
                    <td>
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
                            <span className="pill review">
                              требует проверки
                            </span>
                          ) : null}
                        </>
                      )}
                    </td>
                    <td className="incidents-cell-time" title={r.created_at}>
                      <small>{formatDateTimeDisplay(r.created_at)}</small>
                    </td>
                    <td className="cell-id incidents-cell-id" title={r.incident_id}>
                      <code className="inline incidents-id-code">{r.incident_id}</code>
                    </td>
                    <td className="cell-actions">
                      <button
                        type="button"
                        className="btn btn-ghost incidents-open-btn"
                        onClick={() => toggleIncidentRow(r.incident_id)}
                      >
                        {isOpen ? "Закрыть" : "Открыть"}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>



      {openDetail && (
        <section className="card incidents-layout-detail span-2">
          <div className="card-heading-row">
            <h2>Открытый инцидент</h2>
            <button type="button" className="btn btn-ghost" onClick={backToIncidentsList}>
              Обратно к списку
            </button>
          </div>
          <p>
            <span className="title-accent">{openDetail.title}</span>{" "}
            <span className="pill">{priorityLabel(openDetail.priority)}</span>
          </p>
          <p className="muted">
            <small title={openDetail.created_at}>{formatDateTimeDisplay(openDetail.created_at)}</small> ·{" "}
            <code className="inline">{openDetail.incident_id}</code>
          </p>
          <h3>События</h3>
          <ul className="steps">
            {openDetail.events.map((e) => (
              <li key={e.event_id}>
                <span className={levelClass(e.level)}>[{e.level}]</span> {e.message}
              </li>
            ))}
          </ul>
          <div className="btn-row">
            <button type="button" className="btn btn-primary" onClick={() => void onRunDiagnose()}>
              Запустить диагностику
            </button>
          </div>
          {diagRunMsg && (
            <p className={`msg ${diagRunMsg.t === "ok" ? "ok" : "err"}`}>{diagRunMsg.text}</p>
          )}
        </section>
      )}
    </div>
  );
}
