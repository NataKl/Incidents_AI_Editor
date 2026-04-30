import { Link } from "react-router-dom";
import { useAppShared } from "../AppContext";

export function DiagnosisPage() {
  const { diagnosis, diagnosisIncidentId } = useAppShared();

  return (
    <div className="grid-main">
      <section className="card span-2">
        <h2>
          Диагностика{" "}
          {diagnosis && diagnosisIncidentId ? (
            <>
              инцидента{" "}
              <code className="inline">{diagnosisIncidentId}</code>
            </>
          ) : diagnosis ? (
            <span className="muted">(без привязки к инциденту)</span>
          ) : null}
        </h2>
        <p className="section-intro">
          Результат <code className="inline">POST /api/ai/diagnose</code>. Запуск — со страницы{" "}
          <Link to="/incidents">Инциденты</Link>.
        </p>
        {!diagnosis ? (
          <p className="muted">Пока пусто. Откройте инцидент и нажмите «Запустить диагностику».</p>
        ) : (
          <>
            <h3>Гипотеза причины</h3>
            <p>{diagnosis.root_cause_hypothesis}</p>
            <h3>Уверенность</h3>
            <p>
              <span className="pill">{diagnosis.confidence}</span>
              {diagnosis.needs_review && (
                <span className="pill review" style={{ marginLeft: "0.5rem" }}>
                  требует проверки
                </span>
              )}
            </p>
            <h3>Следующие шаги</h3>
            <ul className="steps">
              {diagnosis.next_steps.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
            {diagnosis.needs_review && (
              <>
                <h3>Каких данных не хватает</h3>
                <ul className="steps">
                  {(() => {
                    const hinted = diagnosis.next_steps.filter((s) =>
                      /уточн|собрать|недостаточно|не хватает/i.test(s),
                    );
                    if (hinted.length) return hinted.map((s, i) => <li key={i}>{s}</li>);
                    return (
                      <li>
                        Низкая уверенность — добавьте логи с request_id, метрики и стеки ошибок.
                      </li>
                    );
                  })()}
                </ul>
                <p className="section-intro" style={{ marginTop: "1rem" }}>
                  Подсказка: корреляционные ID, latency / error rate, полный стек, UTC.
                </p>
              </>
            )}
          </>
        )}
      </section>
    </div>
  );
}
