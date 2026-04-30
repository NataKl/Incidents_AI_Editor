import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiJson, type EventRow } from "../api";
import { useAppShared } from "../AppContext";
import { eventCreatedDisplay, levelClass, parseDdMmYyyyHhMmSsLocalToIso } from "../utils";

export function EventsPage() {
  const navigate = useNavigate();
  const { setIncidentEventIdsDraft } = useAppShared();

  const [events, setEvents] = useState<EventRow[]>([]);
  const [fService, setFService] = useState("");
  const [fLevel, setFLevel] = useState("");
  const [services, setServices] = useState<string[]>([]);
  const [selected, setSelected] = useState<Set<string>>(() => new Set());

  const [evService, setEvService] = useState("api-gateway");
  const [evLevel, setEvLevel] = useState("info");
  const [evMessage, setEvMessage] = useState("");
  const [evTs, setEvTs] = useState("");
  const [evMsg, setEvMsg] = useState<{ t: "ok" | "err"; text: string } | null>(null);

  const [openDetail, setOpenDetail] = useState<EventRow | null>(null);
  const openDetailRef = useRef<HTMLElement | null>(null);
  const eventsListRef = useRef<HTMLElement | null>(null);

  const fetchEvents = useCallback(
    async (signal?: AbortSignal) => {
      const q = new URLSearchParams();
      if (fService.trim()) q.set("service", fService.trim());
      if (fLevel) q.set("level", fLevel);
      const qs = q.toString();
      const path = qs ? `/events?${qs}` : "/events";
      try {
        const { ok, data } = await apiJson<EventRow[]>(path, { signal });
        if (!ok || !Array.isArray(data)) return;
        setEvents(data);
        // Не заменять каталог при пустой выборке — иначе <select>Сервис</select> теряет options
        setServices((prev) => {
          const merged = new Set(prev);
          for (const e of data) merged.add(e.service);
          return [...merged].sort();
        });

        setOpenDetail((prev) => {
          if (!prev) return prev;
          const still = data.find((e) => e.event_id === prev.event_id);
          return still ?? null;
        });
      } catch (err: unknown) {
        if (err instanceof Error && err.name === "AbortError") return;
        throw err;
      }
    },
    [fService, fLevel],
  );

  useEffect(() => {
    const ac = new AbortController();
    void fetchEvents(ac.signal);
    return () => ac.abort();
  }, [fetchEvents]);

  useEffect(() => {
    if (!openDetail) return;
    const frame = window.requestAnimationFrame(() => {
      openDetailRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [openDetail]);

  const serviceOptions = useMemo(() => {
    const opts = new Set(services);
    events.forEach((e) => opts.add(e.service));
    return [...opts].sort();
  }, [services, events]);

  const onCreateEvent = async (e: React.FormEvent) => {
    e.preventDefault();
    setEvMsg(null);
    const parsedTs = parseDdMmYyyyHhMmSsLocalToIso(evTs);
    if (parsedTs === undefined) {
      setEvMsg({
        t: "err",
        text: "Время: укажите DD-MM-YYYY HH:MM:ss или оставьте поле пустым.",
      });
      return;
    }
    const { ok, data } = await apiJson<{ status: string; event_id: string }>(`/events`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        service: evService.trim(),
        level: evLevel,
        message: evMessage,
        ts: parsedTs,
      }),
    });
    if (ok && data && typeof data === "object" && "event_id" in data) {
      setEvMsg({ t: "ok", text: `Событие создано: ${data.event_id}` });
      setEvMessage("");
      void fetchEvents();
    } else {
      const detail =
        typeof data === "object" && data && "detail" in data
          ? JSON.stringify((data as { detail: unknown }).detail)
          : String(data);
      setEvMsg({ t: "err", text: detail || "Ошибка" });
    }
  };

  const toggleSel = (id: string) => {
    setSelected((prev) => {
      const n = new Set(prev);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });
  };

  const goIncidentsWithSelection = () => {
    setIncidentEventIdsDraft([...selected].join("\n"));
    navigate("/incidents");
  };

  const toggleEventRow = (ev: EventRow) => {
    if (openDetail?.event_id === ev.event_id) {
      setOpenDetail(null);
    } else {
      setOpenDetail(ev);
    }
  };

  const backToEventsList = () => {
    setOpenDetail(null);
    queueMicrotask(() => {
      requestAnimationFrame(() => {
        eventsListRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    });
  };

  const onDeleteEvent = async (eventId: string) => {
    if (!window.confirm("Удалить это событие? Связь с инцидентами будет снята.")) return;
    const { ok, status } = await apiJson<{ status?: string }>(
      `/events/${encodeURIComponent(eventId)}`,
      { method: "DELETE" },
    );
    if (!ok) {
      window.alert(status === 404 ? "Событие не найдено." : "Не удалось удалить событие.");
      return;
    }
    setOpenDetail((prev) => (prev?.event_id === eventId ? null : prev));
    setSelected((prev) => {
      const n = new Set(prev);
      n.delete(eventId);
      return n;
    });
    void fetchEvents();
  };

  return (
    <div className="grid-main events-layout">
      <section className="card incidents-toolbar-card">
        <div className="incidents-toolbar-head">
          <h2 className="incidents-toolbar-title">Новое событие</h2>
          <p className="section-intro incidents-toolbar-intro">
            <code className="inline">POST /api/events</code>
          </p>
        </div>
        <form onSubmit={onCreateEvent}>
          <div className="incidents-toolbar-form events-toolbar-form-one-line">
            <label className="field incidents-toolbar-field incidents-toolbar-priority">
              Уровень
              <select value={evLevel} onChange={(e) => setEvLevel(e.target.value)}>
                <option value="info">info</option>
                <option value="warning">warning</option>
                <option value="error">error</option>
              </select>
            </label>
            <label className="field incidents-toolbar-field incidents-toolbar-priority">
              Сервис
              <input
                value={evService}
                onChange={(e) => setEvService(e.target.value)}
                required
                autoComplete="off"
              />
            </label>
            <label className="field incidents-toolbar-field events-toolbar-ts">
              <span className="hint">Время — DD-MM-YYYY HH:MM:ss или пусто</span>
              <input
                value={evTs}
                onChange={(e) => setEvTs(e.target.value)}
                placeholder="30-04-2026 12:00:00"
                autoComplete="off"
              />
            </label>
            <label className="field incidents-toolbar-field events-toolbar-message">
              Сообщение
              <input
                type="text"
                value={evMessage}
                onChange={(e) => setEvMessage(e.target.value)}
                required
                placeholder="Текст события"
                autoComplete="off"
              />
            </label>
            <div className="incidents-toolbar-submit">
              <button type="submit" className="btn btn-primary">
                Отправить событие
              </button>
            </div>
          </div>
        </form>
        {evMsg && <p className={`msg ${evMsg.t === "ok" ? "ok" : "err"}`}>{evMsg.text}</p>}
      </section>

      <section ref={eventsListRef} className="card incidents-layout-table events-table-card">
        <div className="card-heading-row">
          <h2>Последние события</h2>
          <button type="button" className="btn btn-ghost" onClick={() => void fetchEvents()}>
            Обновить
          </button>
        </div>
        <p className="section-intro events-list-intro">
          <code className="inline">GET /api/events</code> — отметьте строки и создайте инцидент.
        </p>
        <div className="events-list-toolbar">
          <label className="field">
            Уровень
            <select value={fLevel} onChange={(e) => setFLevel(e.target.value)}>
              <option value="">все</option>
              <option value="info">info</option>
              <option value="warning">warning</option>
              <option value="error">error</option>
            </select>
          </label>
          <label className="field">
            Сервис
            <select value={fService} onChange={(e) => setFService(e.target.value)}>
              <option value="">все</option>
              {serviceOptions.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
          <div className="events-list-toolbar-actions">
            <button
              type="button"
              className="btn btn-primary"
              disabled={selected.size === 0}
              onClick={goIncidentsWithSelection}
            >
              Создать инцидент из выбранных
            </button>
            <span className="muted">Найдено: {events.length}</span>
            <span className="muted">Выбрано: {selected.size}</span>
          </div>
        </div>
        <div className="table-wrap table-wrap-fit">
          <table className="data events-table">
            <thead>
              <tr>
                <th className="th-chk" />
                <th>Дата создания</th>
                <th>Уровень</th>
                <th>Сервис</th>
                <th>Сообщение</th>
                <th className="th-id">ID события</th>
                <th className="th-actions" />
              </tr>
            </thead>
            <tbody>
              {events.map((ev) => {
                const isOpen = openDetail?.event_id === ev.event_id;
                const createdFmt = eventCreatedDisplay(ev);
                const createdRaw = ev.created_at || ev.ts || "";
                return (
                  <tr key={ev.event_id}>
                    <td className="events-cell-chk">
                      <input
                        type="checkbox"
                        checked={selected.has(ev.event_id)}
                        onChange={() => toggleSel(ev.event_id)}
                        aria-label="Выбрать для инцидента"
                      />
                    </td>
                    <td className="events-cell-time" title={createdRaw || undefined}>
                      <small>{createdFmt}</small>
                    </td>
                    <td className={levelClass(ev.level)} title={ev.level}>
                      {ev.level}
                    </td>
                    <td title={ev.service}>{ev.service}</td>
                    <td className="events-cell-msg" title={ev.message}>
                      <span className="events-msg-text">{ev.message}</span>
                    </td>
                    <td className="cell-id events-cell-id" title={ev.event_id}>
                      <code className="inline events-id-code">{ev.event_id}</code>
                    </td>
                    <td className="cell-actions">
                      <div className="events-actions-cell">
                        <button
                          type="button"
                          className="btn btn-ghost events-open-btn"
                          onClick={() => toggleEventRow(ev)}
                        >
                          {isOpen ? "Закрыть" : "Открыть"}
                        </button>
                        <button
                          type="button"
                          className="btn btn-danger events-delete-btn"
                          onClick={() => void onDeleteEvent(ev.event_id)}
                        >
                          Удалить
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      {openDetail && (
        <section
          ref={openDetailRef}
          className="card incidents-layout-detail span-2"
        >
          <div className="card-heading-row">
            <h2>Открытое событие</h2>
            <button type="button" className="btn btn-ghost" onClick={backToEventsList}>
              Обратно к списку
            </button>
          </div>
          <p>
            <span className={levelClass(openDetail.level)}>{openDetail.level}</span>{" "}
            <span className="pill">{openDetail.service}</span>
          </p>
          <p className="muted">
            <small title={openDetail.created_at || openDetail.ts || undefined}>{eventCreatedDisplay(openDetail)}</small>
          </p>
          <p>
            <code className="inline">{openDetail.event_id}</code>
          </p>
          <h3>Текст</h3>
          <pre className="detail-pre">{openDetail.message}</pre>
          <div className="btn-row">
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => {
                toggleSel(openDetail.event_id);
              }}
            >
              {selected.has(openDetail.event_id) ? "Снять выбор" : "Добавить в выбор"}
            </button>
            <button
              type="button"
              className="btn btn-danger"
              onClick={() => void onDeleteEvent(openDetail.event_id)}
            >
              Удалить событие
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => {
                const ids = new Set(selected);
                ids.add(openDetail.event_id);
                setIncidentEventIdsDraft([...ids].join("\n"));
                navigate("/incidents");
              }}
            >
              Перейти к инциденту с этим событием
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
