import { useCallback, useEffect, useRef, useState } from "react";
import Header from "../components/layout/Header";
import { api } from "../lib/api";

function formatBytes(bytes) {
  const value = Number(bytes);
  if (!Number.isFinite(value) || value < 0) return "Unknown size";
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  if (value < 1024 * 1024 * 1024) {
    return `${(value / (1024 * 1024)).toFixed(1)} MB`;
  }
  return `${(value / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "—"
    : date.toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
}

export default function FileManagerPage({ organizationId }) {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [deletingId, setDeletingId] = useState(null);
  const [documentToDelete, setDocumentToDelete] = useState(null);
  const [confirmDeleteAll, setConfirmDeleteAll] = useState(false);
  const [deletingAll, setDeletingAll] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [versioningId, setVersioningId] = useState(null);
  const fileInput = useRef(null);
  const versionFileInput = useRef(null);
  const versionTargetRef = useRef(null);

  const loadDocuments = useCallback(async () => {
    if (!organizationId) {
      setDocuments([]);
      setLoading(false);
      return;
    }

    setLoading(true);
    setError("");
    try {
      const result = await api.documents(organizationId);
      setDocuments(Array.isArray(result) ? result : []);
    } catch (err) {
      setError(err.message || "Could not load documents.");
    } finally {
      setLoading(false);
    }
  }, [organizationId]);

  useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);

  async function uploadFiles(event) {
    const files = Array.from(event.target.files || []);
    event.target.value = "";
    if (!files.length) return;

    setUploading(true);
    setError("");
    setNotice("");

    let succeeded = 0;
    const failures = [];

    for (const file of files) {
      try {
        await api.uploadDocument(organizationId, file);
        succeeded += 1;
      } catch (err) {
        failures.push(`${file.name}: ${err.message || "Upload failed"}`);
      }
    }

    await loadDocuments();
    setUploading(false);

    if (failures.length) {
      setError(
        [
          succeeded ? `${succeeded} file(s) uploaded successfully.` : "",
          ...failures,
        ].filter(Boolean).join("\n"),
      );
    } else {
      setNotice(`${succeeded} file(s) uploaded successfully.`);
    }
  }

  async function uploadNewVersion(event) {
    const file = event.target.files?.[0];
    event.target.value = "";

    const document = versionTargetRef.current;
    versionTargetRef.current = null;

    if (!file || !document) return;

    setVersioningId(document.id);
    setError("");
    setNotice("");

    try {
      const version = await api.uploadDocumentVersion(
        organizationId,
        document.id,
        file,
      );
      await loadDocuments();
      setNotice(
        `Uploaded version ${version.version_number} for "${document.name}".`,
      );
    } catch (err) {
      setError(err.message || "Could not upload a new document version.");
    } finally {
      setVersioningId(null);
    }
  }

  function removeDocument(document) {
    if (deletingId) return;
    setError("");
    setNotice("");
    setDocumentToDelete(document);
  }

  async function confirmRemoveDocument() {
    const document = documentToDelete;
    if (!document || deletingId) return;

    const name = document.name || "this document";
    setDeletingId(document.id);
    setError("");
    setNotice("");

    try {
      await api.deleteDocument(organizationId, document.id);
      setDocuments((current) => current.filter((item) => item.id !== document.id));
      setNotice(`Deleted "${name}".`);
      setDocumentToDelete(null);
    } catch (err) {
      setError(err.message || "Could not delete the document.");
    } finally {
      setDeletingId(null);
    }
  }

  async function confirmRemoveAllDocuments() {
    if (deletingAll || deletingId || versioningId || uploading) return;

    const snapshot = [...documents];
    if (!snapshot.length) {
      setConfirmDeleteAll(false);
      return;
    }

    setDeletingAll(true);
    setError("");
    setNotice("");

    let succeeded = 0;
    const failures = [];

    try {
      for (const document of snapshot) {
        try {
          await api.deleteDocument(organizationId, document.id);
          succeeded += 1;
          setDocuments((current) =>
            current.filter((item) => item.id !== document.id)
          );
        } catch (err) {
          failures.push(
            `${document.name || document.id}: ${err.message || "Delete failed"}`
          );
        }
      }

      setConfirmDeleteAll(false);

      if (failures.length) {
        setError(
          [
            `${succeeded} of ${snapshot.length} document(s) deleted.`,
            ...failures,
          ].join("\\n")
        );
      } else {
        setNotice(`Successfully deleted all ${succeeded} document(s).`);
      }

      await loadDocuments();
    } catch (err) {
      setNotice("");
      setError(
        `Bulk deletion could not finish cleanly: ${
          err.message || "Please refresh the file list and check the results."
        }`
      );
    } finally {
      setDeletingAll(false);
    }
  }

  return (
    <div className="flex flex-col flex-1 min-h-0">
      <Header title="File Manager" />

      <section className="flex-1 min-h-0 overflow-y-auto p-4 md:p-6">
        <input
          ref={versionFileInput}
          type="file"
          className="hidden"
          onChange={uploadNewVersion}
          aria-label="Choose a replacement document version"
        />
        <div className="max-w-5xl mx-auto">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-6">
            <div>
              <h2 className="text-lg font-semibold text-[var(--foreground)]">
                Organization documents
              </h2>
              <p className="text-sm text-[var(--muted-foreground)] mt-1">
                Upload and manage the files DocPilot can use as knowledge sources.
              </p>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={loadDocuments}
                disabled={loading || uploading}
                className="rounded border border-[var(--border)] px-3 py-2 text-sm text-[var(--foreground)] hover:bg-[var(--muted)] disabled:opacity-50"
              >
                Refresh
              </button>
              <button
                type="button"
                onClick={() => {
                  setError("");
                  setNotice("");
                  setConfirmDeleteAll(true);
                }}
                disabled={
                  loading ||
                  uploading ||
                  Boolean(deletingId || versioningId || deletingAll) ||
                  documents.length === 0
                }
                className="rounded border border-red-500/50 px-3 py-2 text-sm text-red-400 hover:bg-red-500/10 disabled:opacity-50"
              >
                Delete all files
              </button>
              <button
                type="button"
                onClick={() => fileInput.current?.click()}
                disabled={uploading}
                className="rounded bg-[var(--primary)] px-3 py-2 text-sm font-medium text-[var(--primary-foreground)] disabled:opacity-50"
              >
                {uploading ? "Uploading…" : "↑ Upload files"}
              </button>
              <input
                ref={fileInput}
                type="file"
                multiple
                className="hidden"
                onChange={uploadFiles}
                aria-label="Choose files to upload"
              />
            </div>
          </div>

          {error && (
            <div
              role="alert"
              className="mb-4 rounded border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-400 whitespace-pre-wrap"
            >
              {error}
            </div>
          )}

          {notice && (
            <div
              role="status"
              className="mb-4 rounded border border-[var(--border)] p-3 text-sm text-[var(--foreground)]"
            >
              {notice}
            </div>
          )}

          <div className="rounded-lg border border-[var(--border)] overflow-hidden">
            <div className="grid grid-cols-[minmax(0,1fr)_100px_150px_180px] gap-3 px-4 py-3 bg-[var(--card)] border-b border-[var(--border)] text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
              <span>Document</span>
              <span>Size</span>
              <span>Added</span>
              <span className="text-right">Actions</span>
            </div>

            {loading ? (
              <p className="p-6 text-sm text-[var(--muted-foreground)]">
                Loading documents…
              </p>
            ) : documents.length === 0 ? (
              <div className="p-10 text-center">
                <p className="text-sm font-medium text-[var(--foreground)]">
                  No documents yet
                </p>
                <p className="text-xs text-[var(--muted-foreground)] mt-2">
                  Upload a file to start building this organization's knowledge base.
                </p>
                <button
                  type="button"
                  onClick={() => fileInput.current?.click()}
                  disabled={uploading}
                  className="mt-4 rounded border border-[var(--border)] px-3 py-2 text-sm hover:bg-[var(--muted)]"
                >
                  Choose files
                </button>
              </div>
            ) : (
              documents.map((document) => (
                <div
                  key={document.id}
                  className="grid grid-cols-[minmax(0,1fr)_100px_150px_180px] gap-3 items-center px-4 py-3 border-b last:border-b-0 border-[var(--border)]"
                >
                  <div className="min-w-0 flex items-center gap-3">
                    <span className="text-xl" aria-hidden="true">📄</span>
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-[var(--foreground)] truncate">
                        {document.name || "Untitled document"}
                      </p>
                      <p className="text-xs text-[var(--muted-foreground)] truncate">
                        {document.id}
                      </p>
                    </div>
                  </div>
                  <span className="text-xs text-[var(--muted-foreground)]">
                    {formatBytes(document.versions?.[0]?.size_bytes)}
                  </span>
                  <span className="text-xs text-[var(--muted-foreground)]">
                    {formatDate(document.created_at)}
                  </span>
                  <div className="flex justify-end items-center gap-1">
                    <button
                      type="button"
                      onClick={() => {
                        versionTargetRef.current = document;
                        versionFileInput.current?.click();
                      }}
                      disabled={Boolean(versioningId || deletingId)}
                      aria-label={`Upload new version of ${document.name || "document"}`}
                      title="Upload a new version"
                      className="rounded border border-[var(--border)] px-2 py-1 text-xs hover:bg-[var(--muted)] disabled:opacity-50"
                    >
                      {versioningId === document.id ? "Uploading…" : "New version"}
                    </button>
                    <button
                      type="button"
                      onClick={() => removeDocument(document)}
                      disabled={Boolean(deletingId || versioningId)}
                      aria-label={`Delete ${document.name || "document"}`}
                      title="Delete document"
                      className="rounded px-2 py-1 text-xs text-red-400 hover:bg-red-500/10 disabled:opacity-50"
                    >
                      {deletingId === document.id ? "…" : "Delete"}
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>

          <p className="mt-3 text-xs text-[var(--muted-foreground)]">
            Upload permissions depend on your organization role. Large files or unsupported formats may be rejected by the server.
          </p>
        </div>
      </section>
      {confirmDeleteAll && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          onClick={(event) => {
            if (event.target === event.currentTarget && !deletingAll) {
              setConfirmDeleteAll(false);
            }
          }}
        >
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-all-title"
            className="w-full max-w-md rounded-xl border border-[var(--border)] bg-[var(--card)] p-5 shadow-2xl"
          >
            <h2
              id="delete-all-title"
              className="text-base font-semibold text-[var(--foreground)]"
            >
              Delete all files?
            </h2>
            <p className="mt-2 text-sm text-[var(--muted-foreground)]">
              You are about to permanently delete all{" "}
              <strong className="text-[var(--foreground)]">
                {documents.length} document(s)
              </strong>{" "}
              in this organization, including their stored versions. This
              cannot be undone.
            </p>
            {deletingAll && (
              <p role="status" className="mt-3 text-sm text-[var(--muted-foreground)]">
                Deleting documents… {documents.length} document(s) remaining.
              </p>
            )}
            <div className="mt-6 flex justify-end gap-3">
              <button
                type="button"
                className="rounded-md border border-[var(--border)] px-4 py-2 text-sm hover:bg-[var(--muted)] disabled:opacity-50"
                onClick={() => setConfirmDeleteAll(false)}
                disabled={deletingAll}
              >
                Cancel
              </button>
              <button
                type="button"
                className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
                onClick={confirmRemoveAllDocuments}
                disabled={deletingAll || documents.length === 0}
              >
                {deletingAll ? "Deleting…" : "Delete permanently"}
              </button>
            </div>
          </section>
        </div>
      )}
      {documentToDelete && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          onClick={(event) => {
            if (event.target === event.currentTarget && !deletingId) {
              setDocumentToDelete(null);
            }
          }}
        >
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-document-title"
            className="w-full max-w-md rounded-xl border border-[var(--border)] bg-[var(--card)] p-5 shadow-2xl"
          >
            <h2 id="delete-document-title" className="text-base font-semibold text-[var(--foreground)]">
              Delete document?
            </h2>
            <p className="mt-2 break-words text-sm text-[var(--muted-foreground)]">
              Permanently delete <strong className="text-[var(--foreground)]">{documentToDelete.name || "this document"}</strong> and all its stored versions? This action cannot be undone.
            </p>
            <div className="mt-6 flex justify-end gap-3">
              <button
                type="button"
                className="rounded-md border border-[var(--border)] px-4 py-2 text-sm hover:bg-[var(--muted)] disabled:opacity-50"
                onClick={() => setDocumentToDelete(null)}
                disabled={Boolean(deletingId)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
                onClick={confirmRemoveDocument}
                disabled={Boolean(deletingId)}
              >
                {deletingId ? "Deleting…" : "Delete permanently"}
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
