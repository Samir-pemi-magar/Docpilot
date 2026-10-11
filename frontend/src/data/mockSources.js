export const MOCK_SOURCES = [
  {
    id: "s1",
    title: "Infrastructure Runbook v2.4",
    filename: "infra-runbook-v2.4.pdf",
    page: 12,
    section: "§3.1 — Latency SLOs",
    snippet:
      "Payments service SLOs are enforced at the API gateway layer. P99 breaches at 750ms trigger automated alerting via PagerDuty integration. All SLO windows are calculated on a 30-day rolling basis.",
    relevance: 0.97,
    type: "pdf",
  },
  {
    id: "s2",
    title: "Capacity Planning Guide 2024",
    filename: "capacity-planning-2024.pdf",
    page: 34,
    section: "§4 — Database Scaling",
    snippet:
      "Connection pool sizing should account for burst traffic patterns. PgBouncer transaction mode is recommended for services with short-lived queries. Monitor `pg_stat_activity` for waiting clients.",
    relevance: 0.91,
    type: "pdf",
  },
  {
    id: "s3",
    title: "Q3 2024 Infrastructure Review",
    filename: "q3-2024-infra-review.pdf",
    page: 7,
    section: "Checkout Flow SLO Amendment",
    snippet:
      "Following A/B test results showing a 3.2% conversion drop at 200ms latency, the checkout flow SLO was tightened to P95 ≤ 150ms. This supersedes the general payments SLO for this path.",
    relevance: 0.88,
    type: "pdf",
  },
  {
    id: "s4",
    title: "Incident Report INC-1142",
    filename: "inc-1142-postmortem.md",
    page: 1,
    section: "Root Cause & Remediation",
    snippet:
      "Connection pool exhaustion at 120 connections caused 4.2 minutes of degraded checkout performance. Remediation: pool limit raised to 200, circuit breaker threshold added at 85% utilization.",
    relevance: 0.84,
    type: "markdown",
  },
  {
    id: "s5",
    title: "PgBouncer Configuration Reference",
    filename: "pgbouncer-config.md",
    page: 1,
    section: "Transaction Mode Settings",
    snippet:
      "In transaction mode, a server connection is assigned for the duration of a single transaction. Recommended for OLTP workloads. Set `pool_mode = transaction` and `max_client_conn = 300`.",
    relevance: 0.72,
    type: "markdown",
  },
];
