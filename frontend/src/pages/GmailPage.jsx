import { useCallback, useEffect, useMemo, useState } from "react";
import Header from "../components/layout/Header";
import { api } from "../lib/api";

function formatDate(value) {
  if (!value) return "Date unavailable";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Date unavailable"
    : date.toLocaleString([], {
        dateStyle: "medium",
        timeStyle: "short",
      });
}

function ErrorMessage({ children }) {
  if (!children) return null;
  return (
    <div
      role="alert"
      className="mb-4 whitespace-pre-wrap rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300"
    >
      {children}
    </div>
  );
}

export default function GmailPage({
  organizationId,
  callbackNotice = null,
  onDismissCallbackNotice,
}) {
  const [connection, setConnection] = useState(null);
  const [messages, setMessages] = useState([]);
  const [nextPageToken, setNextPageToken] = useState(null);
  const [loadingStatus, setLoadingStatus] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [importingIds, setImportingIds] = useState([]);
  const [selectedIds, setSelectedIds] = useState([]);
  const [filter, setFilter] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [importResults, setImportResults] = useState([]);

  const loadStatus = useCallback(async () => {
    if (!organizationId) return;

    setLoadingStatus(true);
    setError("");

    try {
      const result = await api.gmailStatus(organizationId);
      setConnection(result);
    } catch (err) {
      setConnection(null);
      setError(err.message || "Could not check Gmail connection.");
    } finally {
      setLoadingStatus(false);
    }
  }, [organizationId]);

  const loadMessages = useCallback(async ({ pageToken, append = false } = {}) => {
    if (!organizationId) return;

    setLoadingMessages(true);
    setError("");
    setNotice("");

    try {
      const result = await api.gmailMessages(organizationId, {
        maxResults: 20,
        pageToken,
      });

      const incoming = Array.isArray(result.messages) ? result.messages : [];
      setMessages((previous) => append ? [...previous, ...incoming] : incoming);
      setNextPageToken(result.next_page_token || null);

      if (!append) {
        setSelectedIds([]);
        setImportResults([]);
      }
    } catch (err) {
      setError(err.message || "Could not load Gmail messages.");
    } finally {
      setLoadingMessages(false);
    }
  }, [organizationId]);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  useEffect(() => {
    if (connection?.connected) {
      loadMessages();
    } else {
      setMessages([]);
      setNextPageToken(null);
      setSelectedIds([]);
    }
  }, [connection?.connected, loadMessages]);

  const visibleMessages = useMemo(() => {
    const query = filter.trim().toLowerCase();
    if (!query) return messages;

    return messages.filter((message) =>
      [message.from, message.subject, message.snippet, message.date]
        .some((value) => String(value || "").toLowerCase().includes(query))
    );
  }, [messages, filter]);

  function toggleSelected(messageId) {
    setSelectedIds((previous) =>
      previous.includes(messageId)
        ? previous.filter((id) => id !== messageId)
        : [...previous, messageId]
    );
  }

  function toggleVisible() {
    const visibleIds = visibleMessages.map((message) => message.id);
    const allSelected = visibleIds.length > 0 &&
      visibleIds.every((id) => selectedIds.includes(id));

    setSelectedIds((previous) =>
      allSelected
        ? previous.filter((id) => !visibleIds.includes(id))
        : [...new Set([...previous, ...visibleIds])]
    );
  }

  async function connectGmail() {
    setConnecting(true);
    setError("");
    setNotice("");

    try {
      const result = await api.gmailStartOAuth(organizationId);
      if (!result.authorization_url) {
        throw new Error("The server did not return a Google authorization URL.");
      }

      window.location.assign(result.authorization_url);
    } catch (err) {
      setError(err.message || "Could not start Gmail authorization.");
      setConnecting(false);
    }
  }

  async function importSelected() {
    if (!selectedIds.length || importingIds.length) return;

    const ids = [...selectedIds];
    setImportingIds(ids);
    setError("");
    setNotice("");
    setImportResults([]);

    const results = [];

    for (const id of ids) {
      const message = messages.find((item) => item.id === id);
      try {
        await api.gmailImportMessage(organizationId, id);
        results.push({
          id,
          subject: message?.subject || "(No subject)",
          success: true,
          message: "Imported successfully",
        });
      } catch (err) {
        results.push({
          id,
          subject: message?.subject || "(No subject)",
          success: false,
          message: err.message || "Import failed",
        });
      }

      setImportResults([...results]);
    }

    const succeeded = results.filter((result) => result.success).length;
    const failed = results.length - succeeded;

    setNotice(
      `${succeeded} email(s) imported successfully` +
      (failed ? `; ${failed} failed.` : ".")
    );

    setSelectedIds((previous) => previous.filter(
      (id) => !results.some((result) => result.id === id && result.success)
    ));
    setImportingIds([]);
  }

  const connected = connection?.connected === true;

  return (
    <div className="h-full overflow-y-auto bg-[var(--background)] text-[var(--foreground)]">
      <Header
        title="Gmail"
        description="Bring emails and supported attachments into your DocPilot knowledge base."
      />

      <div className="mx-auto max-w-5xl space-y-5 p-4 md:p-6">
        <section className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
          <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
            <div className="flex items-start gap-3">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-red-500/10 text-2xl">
                ✉️
              </div>
              <div>
                <h2 className="font-semibold">Google Gmail connection</h2>
                <p className="mt-1 text-sm text-[var(--muted-foreground)]">
                  Connect an account to choose which messages DocPilot should process.
                </p>
                <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
                  {loadingStatus ? (
                    <span className="text-[var(--muted-foreground)]">Checking connection…</span>
                  ) : connected ? (
                    <>
                      <span className="rounded-full bg-emerald-500/10 px-2.5 py-1 text-emerald-400">
                        Connected
                      </span>
                      <span className="text-[var(--muted-foreground)]">
                        {connection.email}
                      </span>
                    </>
                  ) : connection?.status === "reauth_required" ? (
                    <span className="rounded-full bg-amber-500/10 px-2.5 py-1 text-amber-300">
                      Reconnection required
                    </span>
                  ) : (
                    <span className="rounded-full bg-[var(--muted)] px-2.5 py-1 text-[var(--muted-foreground)]">
                      Not connected
                    </span>
                  )}
                </div>
              </div>
            </div>

            <div className="flex shrink-0 flex-wrap gap-2">
              <button
                type="button"
                onClick={loadStatus}
                disabled={loadingStatus}
                className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm hover:bg-[var(--muted)] disabled:opacity-50"
              >
                Refresh status
              </button>
              {!connected && (
                <button
                  type="button"
                  onClick={connectGmail}
                  disabled={connecting || loadingStatus}
                  className="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)] disabled:opacity-50"
                >
                  {connecting ? "Opening Google…" : "Connect Gmail"}
                </button>
              )}
            </div>
          </div>

          <p className="mt-4 border-t border-[var(--border)] pt-3 text-xs leading-relaxed text-[var(--muted-foreground)]">
            DocPilot uses the configured Gmail read-only OAuth permission to list and import messages.
            Imported messages become documents; supported attachments can also be imported.
          </p>
        </section>

        {callbackNotice?.type === "cancelled" && (
          <div
            role="status"
            className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-300"
          >
            {callbackNotice.message}
            {onDismissCallbackNotice && (
              <button
                type="button"
                className="ml-3 underline"
                onClick={onDismissCallbackNotice}
              >
                Dismiss
              </button>
            )}
          </div>
        )}

        {callbackNotice?.type === "success" && (
          <div
            role="status"
            className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-300"
          >
            {callbackNotice.message}
            {onDismissCallbackNotice && (
              <button
                type="button"
                className="ml-3 underline"
                onClick={onDismissCallbackNotice}
              >
                Dismiss
              </button>
            )}
          </div>
        )}

        <ErrorMessage>{error}</ErrorMessage>

        {notice && (
          <div
            role="status"
            className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-300"
          >
            {notice}
          </div>
        )}

        {connected && (
          <>
            <section className="rounded-xl border border-[var(--border)] bg-[var(--card)]">
              <div className="flex flex-col gap-3 border-b border-[var(--border)] p-4 md:flex-row md:items-center md:justify-between">
                <div>
                  <h2 className="font-semibold">Choose emails to import</h2>
                  <p className="mt-1 text-xs text-[var(--muted-foreground)]">
                    Showing up to 20 messages per page. Filtering applies to messages already loaded.
                  </p>
                </div>

                <button
                  type="button"
                  onClick={() => loadMessages()}
                  disabled={loadingMessages || importingIds.length > 0}
                  className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm hover:bg-[var(--muted)] disabled:opacity-50"
                >
                  Refresh messages
                </button>
              </div>

              <div className="flex flex-col gap-3 border-b border-[var(--border)] p-4 sm:flex-row sm:items-center">
                <input
                  type="search"
                  value={filter}
                  onChange={(event) => setFilter(event.target.value)}
                  placeholder="Filter loaded emails by sender, subject, or snippet…"
                  aria-label="Filter loaded Gmail messages"
                  className="min-w-0 flex-1 rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm outline-none focus:border-[var(--primary)]"
                />
                <button
                  type="button"
                  onClick={toggleVisible}
                  disabled={!visibleMessages.length}
                  className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm hover:bg-[var(--muted)] disabled:opacity-50"
                >
                  {visibleMessages.length > 0 &&
                    visibleMessages.every((message) => selectedIds.includes(message.id))
                    ? "Deselect visible"
                    : "Select visible"}
                </button>
                <button
                  type="button"
                  onClick={importSelected}
                  disabled={!selectedIds.length || importingIds.length > 0}
                  className="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)] disabled:opacity-50"
                >
                  {importingIds.length
                    ? `Importing ${importResults.length}/${importingIds.length}…`
                    : `Import selected (${selectedIds.length})`}
                </button>
              </div>

              {loadingMessages ? (
                <div className="p-10 text-center text-sm text-[var(--muted-foreground)]">
                  Loading Gmail messages…
                </div>
              ) : visibleMessages.length === 0 ? (
                <div className="p-10 text-center">
                  <p className="text-sm font-medium">
                    {messages.length ? "No matching emails" : "No messages loaded"}
                  </p>
                  <p className="mt-1 text-xs text-[var(--muted-foreground)]">
                    {messages.length
                      ? "Try a different filter."
                      : "Refresh messages to check the connected inbox."}
                  </p>
                </div>
              ) : (
                <div className="divide-y divide-[var(--border)]">
                  {visibleMessages.map((message) => (
                    <label
                      key={message.id}
                      className="flex cursor-pointer gap-3 p-4 transition-colors hover:bg-[var(--muted)]/40"
                    >
                      <input
                        type="checkbox"
                        checked={selectedIds.includes(message.id)}
                        onChange={() => toggleSelected(message.id)}
                        disabled={importingIds.length > 0}
                        className="mt-1 h-4 w-4 shrink-0 accent-[var(--primary)]"
                      />
                      <span className="min-w-0 flex-1">
                        <span className="flex flex-col justify-between gap-1 sm:flex-row">
                          <span className="truncate text-sm font-medium">
                            {message.subject || "(No subject)"}
                          </span>
                          <span className="shrink-0 text-xs text-[var(--muted-foreground)]">
                            {formatDate(message.date)}
                          </span>
                        </span>
                        <span className="mt-1 block truncate text-xs text-[var(--muted-foreground)]">
                          {message.from || "Unknown sender"}
                        </span>
                        <span className="mt-2 block text-sm leading-relaxed text-[var(--muted-foreground)]">
                          {message.snippet || "No preview available."}
                        </span>
                      </span>
                    </label>
                  ))}
                </div>
              )}

              {nextPageToken && (
                <div className="border-t border-[var(--border)] p-4 text-center">
                  <button
                    type="button"
                    onClick={() => loadMessages({ pageToken: nextPageToken, append: true })}
                    disabled={loadingMessages || importingIds.length > 0}
                    className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm hover:bg-[var(--muted)] disabled:opacity-50"
                  >
                    {loadingMessages ? "Loading…" : "Load more messages"}
                  </button>
                </div>
              )}
            </section>

            {importResults.length > 0 && (
              <section className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
                <h2 className="font-semibold">Import results</h2>
                <div className="mt-3 space-y-2">
                  {importResults.map((result) => (
                    <div
                      key={result.id}
                      className="flex flex-col gap-1 rounded-lg border border-[var(--border)] p-3 sm:flex-row sm:items-center sm:justify-between"
                    >
                      <span className="min-w-0 truncate text-sm">{result.subject}</span>
                      <span className={`text-xs ${result.success ? "text-emerald-400" : "text-red-400"}`}>
                        {result.success ? "✓ " : "✕ "}{result.message}
                      </span>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </>
        )}
      </div>
    </div>
  );
}
