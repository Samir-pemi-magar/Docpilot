import Header from "../components/layout/Header";
import EvalDashboard from "../components/eval/EvalDashboard";

export default function DashboardPage({ organizationId }) {
  return (
    <div className="flex flex-col flex-1 min-h-0">
      <Header title="Eval Dashboard" />
      <EvalDashboard organizationId={organizationId} />
    </div>
  );
}
