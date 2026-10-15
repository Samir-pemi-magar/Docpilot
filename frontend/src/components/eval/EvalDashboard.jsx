import { useCallback, useEffect, useState } from "react";
import { api } from "../../lib/api";
import Card from "../ui/Card";
import EvalHistoryChart from "./EvalHistoryChart";

const field =
  "w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm text-[var(--foreground)]";
const button =
  "rounded-md border border-[var(--border)] px-3 py-2 text-sm disabled:opacity-50";

function Panel({ title, children }) {
  return (
    <section className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-5">
      <h2 className="mb-4 text-sm font-semibold text-[var(--foreground)]">{title}</h2>
      {children}
    </section>
  );
}

function Metric({ label, value }) {
  return (
    <Card className="flex flex-col gap-1 px-4 py-3">
      <p className="text-xs text-[var(--muted-foreground)]">{label}</p>
      <p className="text-2xl font-semibold text-[var(--foreground)]">{value}</p>
    </Card>
  );
}

function percentage(value) {
  return typeof value === "number" ? `${(value * 100).toFixed(1)}%` : "N/A";
}

export default function EvalDashboard({ organizationId }) {
  const [datasets, setDatasets] = useState([]);
  const [datasetId, setDatasetId] = useState("");
  const [cases, setCases] = useState([]);
  const [run, setRun] = useState(null);
  const [results, setResults] = useState([]);
  const [historyRuns, setHistoryRuns] = useState([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [question, setQuestion] = useState("");
  const [referenceAnswer, setReferenceAnswer] = useState("");
  const [documentIds, setDocumentIds] = useState("");
  const [topK, setTopK] = useState("5");
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [importing, setImporting] = useState(false);
  const [pendingImport, setPendingImport] = useState(null);
  const [availableDocuments, setAvailableDocuments] = useState([]);
  const [documentMapping, setDocumentMapping] = useState({});
  const [loadingDocuments, setLoadingDocuments] = useState(false);
  const [deletingCaseId, setDeletingCaseId] = useState("");
  const [deletingAllCases, setDeletingAllCases] = useState(false);
  const [showDeleteAllConfirm, setShowDeleteAllConfirm] = useState(false);
  const [caseToDelete, setCaseToDelete] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadDatasets = useCallback(async () => {
    if (!organizationId) return;
    setLoading(true);
    setError("");
    try {
      const data = await api.evaluationDatasets(organizationId);
      setDatasets(data);
      setDatasetId((current) =>
        data.some((item) => item.id === current) ? current : data[0]?.id || ""
      );
    } catch (err) {
      setError(err.message || "Could not load datasets.");
    } finally {
      setLoading(false);
    }
  }, [organizationId]);

  const loadHistory = useCallback(async () => {
    if (!organizationId) {
      setHistoryRuns([]);
      return;
    }
    try {
      setHistoryRuns(await api.evaluationRuns(organizationId, 20));
    } catch (err) {
      setError(err.message || "Could not load evaluation history.");
    }
  }, [organizationId]);

  const loadCases = useCallback(async () => {
    if (!organizationId || !datasetId) {
      setCases([]);
      return;
    }
    try {
      setCases(await api.evaluationCases(organizationId, datasetId));
    } catch (err) {
      setError(err.message || "Could not load questions.");
    }
  }, [organizationId, datasetId]);

  useEffect(() => {
    setDatasets([]);
    setDatasetId("");
    setCases([]);
    setRun(null);
    setResults([]);
    setHistoryRuns([]);
    loadDatasets();
    loadHistory();
  }, [loadDatasets, loadHistory]);

  useEffect(() => {
    setRun(null);
    setResults([]);
    loadCases();
  }, [loadCases]);

  async function createDataset(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    try {
      const created = await api.createEvaluationDataset(organizationId, {
        name: name.trim(),
        description: description.trim() || null,
      });
      setDatasets((items) => [...items, created]);
      setDatasetId(created.id);
      setName("");
      setDescription("");
      setNotice("Dataset created.");
    } catch (err) {
      setError(err.message || "Could not create dataset.");
    }
  }

  async function createCase(event) {
    event.preventDefault();
    if (!datasetId) return;
    setError("");
    setNotice("");
    const ids = documentIds.split(/[,\n]+/).map((id) => id.trim()).filter(Boolean);
    try {
      await api.createEvaluationCase(organizationId, datasetId, {
        question: question.trim(),
        reference_answer: referenceAnswer.trim() || null,
        relevant_document_ids: ids.length ? ids : null,
      });
      setQuestion("");
      setReferenceAnswer("");
      setDocumentIds("");
      setRun(null);
      setResults([]);
      await loadCases();
      setNotice("Question added.");
    } catch (err) {
      setError(err.message || "Could not add question.");
    }
  }

  function isDocumentUuid(value) {
    return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);
  }

  async function stageImportFile(event) {
    const input = event.target;
    const file = input.files?.[0];
    if (!file) return;

    setError("");
    setNotice("");

    if (!datasetId) {
      setError("Choose a dataset before importing cases.");
      input.value = "";
      return;
    }

    if (file.size > 5_000_000) {
      setError("The JSONL file must be no larger than 5 MB.");
      input.value = "";
      return;
    }

    try {
      const content = await file.text();
      const labels = new Set();

      for (const [index, line] of content.split(/\\r?\\n/).entries()) {
        if (!line.trim()) continue;

        let record;
        try {
          record = JSON.parse(line);
        } catch {
          throw new Error(`Invalid JSON on line ${index + 1}.`);
        }

        const references = record?.relevant_document_ids;
        if (Array.isArray(references)) {
          for (const value of references) {
            if (
              typeof value === "string" &&
              value.trim() &&
              !isDocumentUuid(value)
            ) {
              labels.add(value);
            }
          }
        }
      }

      const uniqueLabels = [...labels].sort((a, b) => a.localeCompare(b));
      setPendingImport({
        fileName: file.name,
        content,
        labels: uniqueLabels,
      });
      setDocumentMapping({});

      if (uniqueLabels.length) {
        setLoadingDocuments(true);
        try {
          const documents = await api.documents(organizationId);
          setAvailableDocuments(Array.isArray(documents) ? documents : []);
        } catch (err) {
          setAvailableDocuments([]);
          setError(
            `Could not load organization documents for mapping: ${
              err.message || "request failed"
            }`
          );
        } finally {
          setLoadingDocuments(false);
        }
      } else {
        setAvailableDocuments([]);
      }
    } catch (err) {
      setPendingImport(null);
      setError(err.message || "Could not read the JSONL file.");
    } finally {
      input.value = "";
    }
  }

  async function confirmImport() {
    if (!datasetId || !pendingImport || importing) return;

    setError("");
    setNotice("");
    setImporting(true);

    const mapping = Object.fromEntries(
      pendingImport.labels
        .filter((label) => documentMapping[label])
        .map((label) => [label, documentMapping[label]])
    );

    try {
      const result = await api.importEvaluationCases(
        organizationId,
        datasetId,
        pendingImport.content,
        mapping
      );

      const unresolved = pendingImport.labels.length - Object.keys(mapping).length;
      setPendingImport(null);
      setDocumentMapping({});
      setRun(null);
      setResults([]);
      await loadCases();

      setNotice(
        `Imported ${result.imported_count} evaluation case(s).` +
          (unresolved
            ? ` ${unresolved} benchmark label(s) remain unmapped; cases relying on those labels will not count toward retrieval metrics.`
            : "")
      );
    } catch (err) {
      setError(err.message || "Could not import JSONL cases.");
    } finally {
      setImporting(false);
    }
  }

  function cancelImport() {
    setPendingImport(null);
    setDocumentMapping({});
    setAvailableDocuments([]);
    setError("");
  }

  function removeCase(item) {
    if (!datasetId || !item?.id || deletingCaseId) return;
    setError("");
    setNotice("");
    setCaseToDelete(item);
  }

  async function confirmRemoveCase() {
    const item = caseToDelete;
    if (!datasetId || !item?.id || deletingCaseId) return;

    setError("");
    setNotice("");
    setDeletingCaseId(item.id);

    try {
      await api.deleteEvaluationCase(organizationId, datasetId, item.id);
      setCases((items) => items.filter((saved) => saved.id !== item.id));
      setRun(null);
      setResults([]);
      setNotice("Question deleted. Run the evaluation again to refresh the results.");
      setCaseToDelete(null);
    } catch (err) {
      setError(err.message || "Could not delete question.");
    } finally {
      setDeletingCaseId("");
    }
  }

  async function confirmDeleteAllCases() {
    if (!datasetId || !cases.length || deletingAllCases || deletingCaseId) {
      return;
    }

    setError("");
    setNotice("");
    setDeletingAllCases(true);

    try {
      const response = await api.deleteAllEvaluationCases(
        organizationId,
        datasetId
      );
      const count = response.deleted_count ?? cases.length;
      setCases([]);
      setRun(null);
      setResults([]);
      setCaseToDelete(null);
      setShowDeleteAllConfirm(false);
      setNotice(
        `Deleted ${count} question${count === 1 ? "" : "s"}. Historical evaluation runs were preserved.`
      );
    } catch (err) {
      setError(err.message || "Could not delete all questions.");
    } finally {
      setDeletingAllCases(false);
    }
  }

  async function runEvaluation() {
    if (!datasetId || !cases.length) return;
    setRunning(true);
    setError("");
    setNotice("");
    setRun(null);
    setResults([]);
    try {
      const currentRun = await api.startEvaluationRun(
        organizationId, datasetId, Number(topK)
      );
      setRun(currentRun);
      const data = await api.evaluationRunResults(
        organizationId, datasetId, currentRun.id
      );
      setResults(data);
      await loadHistory();
      setNotice("Evaluation results loaded from the backend.");
    } catch (err) {
      setError(err.message || "Evaluation failed.");
    } finally {
      setRunning(false);
    }
  }

  const metrics = run?.metrics || {};
  const evaluated = Number(metrics.retrieval_evaluated_cases || 0);
  const metricsAvailable = evaluated > 0;

  return (
    <div className="flex-1 min-h-0 overflow-y-auto p-4 md:p-6">
      <div className="mx-auto flex max-w-6xl flex-col gap-5">
        <header>
          <h1 className="text-xl font-semibold text-[var(--foreground)]">Evaluation</h1>
          <p className="mt-1 text-sm text-[var(--muted-foreground)]">
            Test retrieval and answers using your organization’s documents.
          </p>
        </header>

        {error && <p role="alert" className="rounded border border-red-500/40 p-3 text-sm text-red-500">{error}</p>}
        {notice && <p role="status" className="rounded border border-[var(--border)] p-3 text-sm">{notice}</p>}

        <Panel title="1. Datasets">
          <div className="grid gap-5 md:grid-cols-2">
            <div>
              <label className="mb-1 block text-xs text-[var(--muted-foreground)]">Select dataset</label>
              <select className={field} value={datasetId} onChange={(e) => setDatasetId(e.target.value)} disabled={loading}>
                <option value="">Choose a dataset</option>
                {datasets.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
              {!loading && !datasets.length && <p className="mt-2 text-xs text-[var(--muted-foreground)]">No datasets yet.</p>}
            </div>
            <form className="flex flex-col gap-2" onSubmit={createDataset}>
              <input className={field} placeholder="New dataset name" value={name} onChange={(e) => setName(e.target.value)} required maxLength={200} />
              <input className={field} placeholder="Description (optional)" value={description} onChange={(e) => setDescription(e.target.value)} />
              <button className={button} type="submit" disabled={!name.trim()}>Create dataset</button>
            </form>
          </div>
        </Panel>

        <Panel title="2. Add questions">
          <form className="flex flex-col gap-3" onSubmit={createCase}>
            <textarea className={field} rows={2} placeholder="Question about your documents" value={question} onChange={(e) => setQuestion(e.target.value)} required disabled={!datasetId} maxLength={10000} />
            <textarea className={field} rows={2} placeholder="Reference answer (optional)" value={referenceAnswer} onChange={(e) => setReferenceAnswer(e.target.value)} disabled={!datasetId} maxLength={20000} />
            <textarea className={field} rows={2} placeholder="Relevant document UUIDs, separated by commas (optional)" value={documentIds} onChange={(e) => setDocumentIds(e.target.value)} disabled={!datasetId} />
            <p className="text-xs text-[var(--muted-foreground)]">
              Relevant document IDs enable retrieval metrics. Leave them blank if you only want to inspect generated answers and sources.
            </p>
            <div><button className={button} type="submit" disabled={!datasetId || !question.trim()}>Add question</button></div>
          </form>
          <div className="mt-5 border-t border-[var(--border)] pt-4">
            <h3 className="mb-2 text-xs font-semibold">Import JSONL benchmark</h3>
            <p className="mb-3 text-xs text-[var(--muted-foreground)]">
              Upload a .jsonl file with one JSON object per line. Each object
              needs a question field. Benchmark metadata is preserved.
              You can map benchmark document labels to documents in this
              organization before importing. Maximum file size: 5 MB.
            </p>
            <input
              className={`${field} mb-3`}
              type="file"
              accept=".jsonl,.ndjson,application/x-ndjson,application/json"
              onChange={stageImportFile}
              disabled={!datasetId || importing || Boolean(pendingImport)}
              aria-label="Select evaluation cases JSONL file"
            />

            {pendingImport && (
              <div className="flex flex-col gap-3 rounded-md border border-[var(--border)] p-3">
                <div>
                  <p className="text-sm font-medium">{pendingImport.fileName}</p>
                  <p className="mt-1 text-xs text-[var(--muted-foreground)]">
                    {pendingImport.labels.length
                      ? `${pendingImport.labels.length} unique benchmark document label(s) found. Map each label to the matching document.`
                      : "No non-UUID document labels found. You can import this file directly."}
                  </p>
                </div>

                {loadingDocuments && (
                  <p role="status" className="text-xs text-[var(--muted-foreground)]">
                    Loading organization documents…
                  </p>
                )}

                {pendingImport.labels.map((label) => (
                  <label key={label} className="flex flex-col gap-1 text-xs">
                    <span className="font-medium">{label}</span>
                    <select
                      className={field}
                      value={documentMapping[label] || ""}
                      onChange={(event) =>
                        setDocumentMapping((current) => ({
                          ...current,
                          [label]: event.target.value,
                        }))
                      }
                      disabled={loadingDocuments || importing}
                    >
                      <option value="">Leave unmapped</option>
                      {availableDocuments.map((document) => (
                        <option key={document.id} value={document.id}>
                          {document.name} — {document.id}
                        </option>
                      ))}
                    </select>
                  </label>
                ))}

                {pendingImport.labels.length > 0 && (
                  <p className="text-xs text-[var(--muted-foreground)]">
                    Unmapped labels are preserved as metadata, but they do not
                    count as retrieval ground truth. Only map a label when
                    you have confirmed which document it represents.
                  </p>
                )}

                <div className="flex flex-wrap gap-2">
                  <button
                    className={button}
                    type="button"
                    onClick={confirmImport}
                    disabled={importing || loadingDocuments}
                  >
                    {importing ? "Importing…" : "Confirm import"}
                  </button>
                  <button
                    className={button}
                    type="button"
                    onClick={cancelImport}
                    disabled={importing}
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>
          <div className="mt-5 border-t border-[var(--border)] pt-4">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <h3 className="text-xs font-semibold">Questions ({cases.length})</h3>
              <button
                className={`${button} py-1 text-xs text-red-500`}
                type="button"
                onClick={() => setShowDeleteAllConfirm(true)}
                disabled={
                  !datasetId ||
                  !cases.length ||
                  running ||
                  importing ||
                  Boolean(deletingCaseId) ||
                  deletingAllCases
                }
              >
                Delete all questions
              </button>
            </div>
            {!cases.length ? <p className="text-sm text-[var(--muted-foreground)]">Add at least one question.</p> : (
              <ol className="flex flex-col gap-2">
                {cases.map((item, i) => (
                  <li key={item.id} className="rounded border border-[var(--border)] p-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-xs text-[var(--muted-foreground)]">
                          Question {i + 1}
                          {item.metadata?.case_id && ` · ${item.metadata.case_id}`}
                        </p>
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          {[
                            ["Category", item.metadata?.category],
                            ["Difficulty", item.metadata?.difficulty],
                            ["Expected behavior", item.metadata?.expected_behavior],
                            [
                              "Answerable",
                              typeof item.metadata?.answerable === "boolean"
                                ? item.metadata.answerable ? "Yes" : "No"
                                : null,
                            ],
                          ].filter(([, value]) => value != null && value !== "").map(([label, value]) => (
                            <span
                              key={label}
                              className="rounded-md border border-[var(--border)] px-2 py-1 text-xs text-[var(--muted-foreground)]"
                            >
                              <span className="font-medium text-[var(--foreground)]">{label}:</span>{" "}
                              {String(value)}
                            </span>
                          ))}
                        </div>
                      </div>
                      <button
                        className={`${button} py-1 text-xs text-red-500`}
                        type="button"
                        onClick={() => removeCase(item)}
                        disabled={Boolean(deletingCaseId) || deletingAllCases}
                      >
                        {deletingCaseId === item.id ? "Deleting…" : "Delete"}
                      </button>
                    </div>
                    <p className="mt-1 whitespace-pre-wrap text-sm">{item.question}</p>
                    <p className="mt-2 text-xs text-[var(--muted-foreground)]">
                      {item.relevant_document_ids?.length
                        ? `${item.relevant_document_ids.length} resolved relevance label(s)`
                        : item.metadata?.relevant_document_ids?.length
                          ? `Document references: ${item.metadata.relevant_document_ids.join(", ")} (not mapped to DocPilot document IDs)`
                          : "No relevance labels"}
                    </p>

                    {item.metadata && Object.keys(item.metadata).length > 0 && (
                      <details className="mt-3 rounded border border-[var(--border)] p-3">
                        <summary className="cursor-pointer text-xs font-semibold">
                          Benchmark details ({Object.keys(item.metadata).length} fields)
                        </summary>
                        <dl className="mt-3 flex flex-col gap-3">
                          {Object.entries(item.metadata).map(([key, value]) => (
                            <div key={key} className="min-w-0">
                              <dt className="text-xs font-semibold">
                                {key.replace(/_/g, " ")}
                              </dt>
                              <dd className="mt-1 whitespace-pre-wrap break-words text-xs text-[var(--muted-foreground)]">
                                {value === null
                                  ? "null"
                                  : typeof value === "object"
                                    ? JSON.stringify(value, null, 2)
                                    : String(value)}
                              </dd>
                            </div>
                          ))}
                        </dl>
                      </details>
                    )}
                  </li>
                ))}
              </ol>
            )}
          </div>
        </Panel>

        <Panel title="3. Run evaluation">
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label className="mb-1 block text-xs text-[var(--muted-foreground)]">Top-k</label>
              <input className={field} style={{ width: 110 }} type="number" min="1" max="100" value={topK} onChange={(e) => setTopK(e.target.value)} />
            </div>
            <button className={button} type="button" onClick={runEvaluation} disabled={!datasetId || !cases.length || running || !Number.isInteger(Number(topK)) || Number(topK) < 1 || Number(topK) > 100}>
              {running ? "Running…" : "Run evaluation"}
            </button>
          </div>
          {running && <p className="mt-3 text-sm text-[var(--muted-foreground)]">The backend is processing your questions. Please wait.</p>}
        </Panel>

        <Panel title="4. Recent retrieval history">
          <EvalHistoryChart runs={historyRuns} />
        </Panel>

        {run && <>
          <Panel title={`5. Run summary — ${run.status}`}>
            <p className="mb-3 break-all text-xs text-[var(--muted-foreground)]">Run ID: {run.id}</p>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Metric label="Hit rate@k" value={metricsAvailable ? percentage(metrics.hit_rate_at_k) : "N/A"} />
              <Metric label="Recall@k" value={metricsAvailable ? percentage(metrics.recall_at_k) : "N/A"} />
              <Metric label="Reciprocal rank" value={metricsAvailable ? percentage(metrics.reciprocal_rank) : "N/A"} />
              <Metric label="Completed cases" value={`${run.completed_cases}/${run.total_cases}`} />
            </div>
            <p className="mt-3 text-xs text-[var(--muted-foreground)]">
              {run.failed_cases} failed · {evaluated} case(s) used for retrieval metrics.
              {!metricsAvailable && " Metrics need relevance labels (relevant document IDs)."}
            </p>
            <div className="mt-4 rounded-md bg-[var(--background)] p-3 text-xs leading-relaxed text-[var(--muted-foreground)]">
              <p><strong>How to read these scores</strong></p>
              <p className="mt-1"><strong>Hit rate@k:</strong> For how many labelled questions did at least one relevant document appear in the top-k results?</p>
              <p className="mt-1"><strong>Recall@k:</strong> How many of the labelled relevant documents were found in the top-k results?</p>
              <p className="mt-1"><strong>Reciprocal rank:</strong> How high was the first relevant document in the results? Higher is better.</p>
              <p className="mt-2">These scores measure retrieval, not whether the generated answer is correct. Only questions with relevant document IDs contribute to these retrieval metrics.</p>
            </div>
            {run.error_message && <p className="mt-3 text-sm text-red-500">{run.error_message}</p>}
          </Panel>

          <Panel title="6. Results">
            {!results.length ? <p className="text-sm text-[var(--muted-foreground)]">No result records were returned.</p> : (
              <div className="flex flex-col gap-4">
                {results.map((result, i) => (
                  <article key={result.id} className="rounded border border-[var(--border)] p-4">
                    <div className="flex flex-wrap justify-between gap-2">
                      <h3 className="text-sm font-semibold">Question {i + 1}</h3>
                      <span className="text-xs text-[var(--muted-foreground)]">
                        {result.status}{result.duration_ms != null ? ` · ${result.duration_ms} ms` : ""}
                      </span>
                    </div>
                    <p className="mt-2 whitespace-pre-wrap text-sm">{result.question_snapshot}</p>
                    {result.reference_answer_snapshot && <p className="mt-3 whitespace-pre-wrap text-sm"><strong>Reference:</strong> {result.reference_answer_snapshot}</p>}
                    {result.case_metadata_snapshot &&
                      Object.keys(result.case_metadata_snapshot).length > 0 && (
                        <details className="mt-3 rounded border border-[var(--border)] p-3">
                          <summary className="cursor-pointer text-xs font-semibold">
                            Benchmark metadata ({Object.keys(result.case_metadata_snapshot).length} fields)
                          </summary>
                          <dl className="mt-3 flex flex-col gap-3">
                            {Object.entries(result.case_metadata_snapshot).map(([key, value]) => (
                              <div key={key} className="min-w-0">
                                <dt className="text-xs font-semibold">
                                  {key.replace(/_/g, " ")}
                                </dt>
                                <dd className="mt-1 whitespace-pre-wrap break-words text-xs text-[var(--muted-foreground)]">
                                  {value === null
                                    ? "null"
                                    : typeof value === "object"
                                      ? JSON.stringify(value, null, 2)
                                      : String(value)}
                                </dd>
                              </div>
                            ))}
                          </dl>
                        </details>
                      )}
                    <div className="mt-3">
                      <p className="text-xs font-semibold">Generated answer</p>
                      <p className="mt-1 whitespace-pre-wrap text-sm">{result.actual_answer || "No answer produced."}</p>
                    </div>
                    {result.error_message && <p className="mt-3 whitespace-pre-wrap text-sm text-red-500">{result.error_message}</p>}
                    {result.metrics && Object.keys(result.metrics).length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {Object.entries(result.metrics).map(([key, value]) => (
                          <span key={key} className="rounded border border-[var(--border)] px-2 py-1 text-xs">{key}: {typeof value === "number" ? value.toFixed(3) : String(value)}</span>
                        ))}
                      </div>
                    )}
                    <div className="mt-4 border-t border-[var(--border)] pt-3">
                      <p className="mb-1 text-xs font-semibold">Retrieved sources ({result.retrieved_sources?.length || 0})</p>
                      <p className="mb-2 text-xs text-[var(--muted-foreground)]">Read the generated answer and reference first. Open a source below only when you want to check the evidence used.</p>
                      {!result.retrieved_sources?.length ? <p className="text-xs text-[var(--muted-foreground)]">No sources returned.</p> : (
                        <div className="flex flex-col gap-2">
                          {result.retrieved_sources.map((source, j) => (
                            <details key={source.chunk_id || j} className="rounded bg-[var(--background)] p-3">
                              <summary className="cursor-pointer text-xs font-medium">
                                {j + 1}. {source.document_name || source.document_id || "Unknown document"}{source.chunk_index != null ? ` · Chunk ${source.chunk_index}` : ""}
                                {typeof source.distance === "number" ? ` · Distance ${source.distance.toFixed(4)}` : ""}
                              </summary>
                              <p className="mt-2 whitespace-pre-wrap text-xs leading-relaxed text-[var(--muted-foreground)]">{source.text || "No source text available."}</p>
                            </details>
                          ))}
                        </div>
                      )}
                    </div>
                  </article>
                ))}
              </div>
            )}
          </Panel>
        </>}
      </div>
      {showDeleteAllConfirm && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          onClick={(event) => {
            if (event.target === event.currentTarget && !deletingAllCases) {
              setShowDeleteAllConfirm(false);
            }
          }}
        >
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-all-questions-title"
            className="w-full max-w-lg rounded-xl border border-[var(--border)] bg-[var(--card)] p-5 shadow-2xl"
          >
            <h2
              id="delete-all-questions-title"
              className="text-base font-semibold text-[var(--foreground)]"
            >
              Delete all questions?
            </h2>
            <p className="mt-2 text-sm text-[var(--muted-foreground)]">
              This will permanently delete all {cases.length} question{cases.length === 1 ? "" : "s"} in the selected dataset. This action cannot be undone.
            </p>
            <p className="mt-2 text-sm text-[var(--muted-foreground)]">
              The dataset, source documents, and historical evaluation runs will be preserved. Saved historical results will remain available.
            </p>
            <div className="mt-6 flex justify-end gap-3">
              <button
                type="button"
                className="rounded-md border border-[var(--border)] px-4 py-2 text-sm hover:bg-[var(--muted)] disabled:opacity-50"
                onClick={() => setShowDeleteAllConfirm(false)}
                disabled={deletingAllCases}
              >
                Cancel
              </button>
              <button
                type="button"
                className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
                onClick={confirmDeleteAllCases}
                disabled={deletingAllCases || !cases.length}
              >
                {deletingAllCases ? "Deleting questions…" : `Delete ${cases.length} questions`}
              </button>
            </div>
          </section>
        </div>
      )}
      {caseToDelete && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          onClick={(event) => {
            if (event.target === event.currentTarget && !deletingCaseId) {
              setCaseToDelete(null);
            }
          }}
        >
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-question-title"
            className="w-full max-w-lg rounded-xl border border-[var(--border)] bg-[var(--card)] p-5 shadow-2xl"
          >
            <h2 id="delete-question-title" className="text-base font-semibold text-[var(--foreground)]">
              Delete question?
            </h2>
            <p className="mt-2 text-sm text-[var(--muted-foreground)]">
              This permanently removes the question from the selected evaluation dataset. This action cannot be undone.
            </p>
            <blockquote className="mt-3 max-h-40 overflow-y-auto whitespace-pre-wrap break-words rounded-md bg-[var(--background)] p-3 text-sm text-[var(--foreground)]">
              {caseToDelete.question}
            </blockquote>
            <div className="mt-6 flex justify-end gap-3">
              <button
                type="button"
                className="rounded-md border border-[var(--border)] px-4 py-2 text-sm hover:bg-[var(--muted)] disabled:opacity-50"
                onClick={() => setCaseToDelete(null)}
                disabled={Boolean(deletingCaseId)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
                onClick={confirmRemoveCase}
                disabled={Boolean(deletingCaseId)}
              >
                {deletingCaseId ? "Deleting…" : "Delete question"}
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
