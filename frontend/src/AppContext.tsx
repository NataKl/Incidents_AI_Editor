import {
  createContext,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { DiagnosisView } from "./api";

export type AppShared = {
  diagnosis: DiagnosisView | null;
  setDiagnosis: (v: DiagnosisView | null) => void;
  diagnosisIncidentId: string | null;
  setDiagnosisIncidentId: (v: string | null) => void;
  incidentEventIdsDraft: string;
  setIncidentEventIdsDraft: (v: string) => void;
};

const Ctx = createContext<AppShared | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [diagnosis, setDiagnosis] = useState<DiagnosisView | null>(null);
  const [diagnosisIncidentId, setDiagnosisIncidentId] = useState<string | null>(null);
  const [incidentEventIdsDraft, setIncidentEventIdsDraft] = useState("");

  const value = useMemo(
    () => ({
      diagnosis,
      setDiagnosis,
      diagnosisIncidentId,
      setDiagnosisIncidentId,
      incidentEventIdsDraft,
      setIncidentEventIdsDraft,
    }),
    [diagnosis, diagnosisIncidentId, incidentEventIdsDraft],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAppShared(): AppShared {
  const v = useContext(Ctx);
  if (!v) throw new Error("AppProvider required");
  return v;
}
