import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./Layout";
import { DashboardPage } from "./pages/DashboardPage";
import { DiagnosisPage } from "./pages/DiagnosisPage";
import { EventsPage } from "./pages/EventsPage";
import { IncidentsPage } from "./pages/IncidentsPage";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Navigate to="/events" replace />} />
        <Route path="/events" element={<EventsPage />} />
        <Route path="/incidents" element={<IncidentsPage />} />
        <Route path="/diagnosis" element={<DiagnosisPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/admin" element={<Navigate to="/dashboard" replace />} />
        <Route path="*" element={<Navigate to="/events" replace />} />
      </Route>
    </Routes>
  );
}
