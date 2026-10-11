export const MOCK_MESSAGES = [
  {
    id: "1",
    role: "user",
    content: "What are the latency SLOs defined in the infrastructure runbook for the payments service?",
    timestamp: "10:42 AM",
  },
  {
    id: "2",
    role: "assistant",
    content:
      "According to the infrastructure runbook (v2.4), the payments service has the following latency SLOs defined:\n\n**P50 latency:** ≤ 80ms at the API gateway\n**P95 latency:** ≤ 220ms end-to-end\n**P99 latency:** ≤ 500ms, with a 30-day rolling window\n\nThe runbook also specifies that latency breaches exceeding **750ms** at P99 trigger an automatic PagerDuty alert to the on-call engineer. [1]\n\nFor the checkout flow specifically, a tighter SLO of P95 ≤ 150ms is enforced due to its direct impact on conversion. This was introduced in the Q3 2024 infrastructure review. [2][3]",
    timestamp: "10:42 AM",
    citations: [
      { ref: 1, sourceId: "s1" },
      { ref: 2, sourceId: "s2" },
      { ref: 3, sourceId: "s3" },
    ],
  },
  {
    id: "3",
    role: "user",
    content: "Does the runbook mention anything about database connection pool limits during high traffic?",
    timestamp: "10:44 AM",
  },
  {
    id: "4",
    role: "assistant",
    content:
      "Yes. Section 4.2 of the runbook addresses connection pool configuration under load. Key points:\n\n- The PostgreSQL connection pool is capped at **200 connections per replica** via PgBouncer in transaction mode\n- During high-traffic events, a **circuit breaker** activates at 85% pool utilization, queuing new requests rather than rejecting them\n- Pool size was doubled in November 2024 after a Black Friday incident (see incident report INC-1142) [1]\n\nThe runbook recommends monitoring the `pg_stat_activity` view and setting up alerts when `waiting` connections exceed 20. It also references a separate capacity planning document for scaling guidelines. [2]",
    timestamp: "10:44 AM",
    citations: [
      { ref: 1, sourceId: "s4" },
      { ref: 2, sourceId: "s2" },
    ],
  },
];

export const STREAMING_RESPONSE = {
  id: "streaming",
  role: "assistant",
  content: "",
  timestamp: "now",
  citations: [],
  isStreaming: true,
};
