export function levelClass(l: string): string {
  return `level-${l}`;
}

/** Соответствует полю priority в API (1–5). */
export const PRIORITY_OPTIONS = [
  { value: 1, label: "Блокирующий" },
  { value: 2, label: "Критичный" },
  { value: 3, label: "Срочный" },
  { value: 4, label: "Средний" },
  { value: 5, label: "Низкий" },
] as const;

export function priorityLabel(p: number): string {
  const row = PRIORITY_OPTIONS.find((o) => o.value === p);
  return row ? `${row.value} — ${row.label}` : String(p);
}

/** Цветовой класс приоритета 1–5 для дашборда (тепловая шкала, без текстовых подписей уровней). */
export function priorityHeatClass(p: number): string {
  if (p >= 1 && p <= 5) return `priority-heat priority-heat--${p}`;
  return "priority-heat priority-heat--neutral";
}

const DD_MM_YYYY_HH_MM_SS = /^(\d{2})-(\d{2})-(\d{4})\s+(\d{2}):(\d{2}):(\d{2})$/;

/** Ввод формы «Время»: DD-MM-YYYY HH:MM:ss в локальной зоне → ISO UTC для API. Пустая строка → null. */
export function parseDdMmYyyyHhMmSsLocalToIso(raw: string): string | null | undefined {
  const s = raw.trim();
  if (s === "") return null;
  const m = s.match(DD_MM_YYYY_HH_MM_SS);
  if (!m) return undefined;
  const day = Number(m[1]);
  const month = Number(m[2]);
  const year = Number(m[3]);
  const hour = Number(m[4]);
  const minute = Number(m[5]);
  const second = Number(m[6]);
  if (
    month < 1 ||
    month > 12 ||
    day < 1 ||
    day > 31 ||
    hour > 23 ||
    minute > 59 ||
    second > 59
  ) {
    return undefined;
  }
  const d = new Date(year, month - 1, day, hour, minute, second);
  if (d.getFullYear() !== year || d.getMonth() !== month - 1 || d.getDate() !== day) {
    return undefined;
  }
  return d.toISOString();
}

/** Локальное отображение: dd-mm-yyyy hh:mm:ss (24 часа). */
export function formatDateTimeDisplay(raw: string | null | undefined): string {
  if (raw == null || String(raw).trim() === "") return "—";
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return String(raw);
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const yyyy = d.getFullYear();
  const hh = String(d.getHours()).padStart(2, "0");
  const min = String(d.getMinutes()).padStart(2, "0");
  const ss = String(d.getSeconds()).padStart(2, "0");
  return `${dd}-${mm}-${yyyy} ${hh}:${min}:${ss}`;
}

/** Колонка «Дата создания» для события: created_at, иначе ts. */
export function eventCreatedDisplay(ev: { created_at: string; ts: string | null }): string {
  return formatDateTimeDisplay(ev.created_at || ev.ts);
}
