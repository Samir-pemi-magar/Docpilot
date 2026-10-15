import { useCallback, useEffect, useState } from "react";
import AppShell from "./components/layout/AppShell";
import ChatPage from "./pages/ChatPage";
import DashboardPage from "./pages/DashboardPage";
import FileManagerPage from "./pages/FileManagerPage";
import { api, clearAccessToken, getAccessToken, setAccessToken } from "./lib/api";

function LoginPage({ onLogin, onRegister }) {
  const [mode, setMode] = useState("login");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const registering = mode === "register";

  async function submit(event) {
    event.preventDefault();
    setError("");
    setBusy(true);

    try {
      if (registering) {
        await onRegister(fullName.trim(), email.trim(), password);
      } else {
        await onLogin(email.trim(), password);
      }
    } catch (err) {
      setError(err.message || (registering ? "Registration failed." : "Login failed."));
    } finally {
      setBusy(false);
    }
  }

  function switchMode() {
    setMode(registering ? "login" : "register");
    setError("");
  }

  return (
    <main className="min-h-screen flex items-center justify-center bg-[var(--background)] px-4 py-10">
      <form
        onSubmit={submit}
        className="w-full max-w-sm rounded-lg border border-[var(--border)] bg-[var(--card)] p-6"
      >
        <div className="flex items-center gap-2 mb-6">
          <div className="w-8 h-8 rounded bg-[var(--primary)] flex items-center justify-center">
            <span className="text-xs font-bold text-[var(--primary-foreground)]">DP</span>
          </div>
          <div>
            <h1 className="text-base font-semibold text-[var(--foreground)]">DocPilot</h1>
            <p className="text-xs text-[var(--muted-foreground)]">
              {registering ? "Create your account" : "Sign in to your workspace"}
            </p>
          </div>
        </div>

        {registering && (
          <>
            <label className="block text-xs mb-1.5 text-[var(--muted-foreground)]" htmlFor="full-name">
              Full name
            </label>
            <input
              id="full-name"
              type="text"
              autoComplete="name"
              required
              maxLength={255}
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
              className="w-full rounded border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm text-[var(--foreground)] outline-none mb-4"
            />
          </>
        )}

        <label className="block text-xs mb-1.5 text-[var(--muted-foreground)]" htmlFor="email">
          Email
        </label>
        <input
          id="email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          className="w-full rounded border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm text-[var(--foreground)] outline-none mb-4"
        />

        <label className="block text-xs mb-1.5 text-[var(--muted-foreground)]" htmlFor="password">
          Password
        </label>
        <input
          id="password"
          type="password"
          autoComplete={registering ? "new-password" : "current-password"}
          required
          minLength={registering ? 8 : undefined}
          maxLength={128}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          className="w-full rounded border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm text-[var(--foreground)] outline-none mb-2"
        />
        {registering && (
          <p className="text-xs text-[var(--muted-foreground)] mb-4">
            Use at least 8 characters.
          </p>
        )}

        {error && (
          <p role="alert" className="text-xs text-red-400 mb-3">{error}</p>
        )}

        <button
          type="submit"
          disabled={busy}
          className="w-full rounded bg-[var(--primary)] px-3 py-2 text-sm font-medium text-[var(--primary-foreground)] disabled:opacity-50"
        >
          {busy
            ? (registering ? "Creating account…" : "Signing in…")
            : (registering ? "Create account" : "Sign in")}
        </button>

        <p className="mt-4 text-center text-xs text-[var(--muted-foreground)]">
          {registering ? "Already have an account?" : "New to DocPilot?"}{" "}
          <button
            type="button"
            onClick={switchMode}
            className="font-medium text-[var(--foreground)] underline underline-offset-2"
          >
            {registering ? "Sign in" : "Create account"}
          </button>
        </p>
      </form>
    </main>
  );
}

function DeleteAccountControl({ onDeleted }) {
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  function closeDialog() {
    if (busy) return;
    setOpen(false);
    setPassword("");
    setConfirmed(false);
    setError("");
  }

  async function submit(event) {
    event.preventDefault();
    if (busy || !password || !confirmed) return;

    setBusy(true);
    setError("");

    try {
      await api.deleteAccount(password);
      onDeleted();
    } catch (err) {
      setError(err.message || "Account deletion failed. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={() => {
          setError("");
          setOpen(true);
        }}
        className="text-xs text-red-400 transition hover:text-red-300"
      >
        Delete account
      </button>

      {open && (
        <div
          className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget && !busy) closeDialog();
          }}
        >
          <section
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="delete-account-title"
            aria-describedby="delete-account-description"
            className="w-full max-w-md rounded-xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-2xl"
          >
            <h2
              id="delete-account-title"
              className="text-base font-semibold text-[var(--foreground)]"
            >
              Delete your account?
            </h2>

            <p
              id="delete-account-description"
              className="mt-3 text-sm leading-6 text-[var(--muted-foreground)]"
            >
              This permanently deletes your account and cannot be undone.
              Shared organization documents and evaluation history are
              preserved, but your personal conversations will be deleted.
              You must transfer or delete any organizations you own first.
            </p>

            <form onSubmit={submit} className="mt-5 space-y-4">
              <div>
                <label
                  htmlFor="delete-account-password"
                  className="mb-1.5 block text-xs text-[var(--muted-foreground)]"
                >
                  Enter your password to continue
                </label>
                <input
                  id="delete-account-password"
                  type="password"
                  autoComplete="current-password"
                  required
                  maxLength={128}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  disabled={busy}
                  className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm text-[var(--foreground)] disabled:opacity-50"
                />
              </div>

              <label className="flex items-start gap-2 text-sm text-[var(--foreground)]">
                <input
                  type="checkbox"
                  checked={confirmed}
                  onChange={(event) => setConfirmed(event.target.checked)}
                  disabled={busy}
                  className="mt-1 accent-red-500"
                />
                <span>
                  I understand that deleting my account is permanent and
                  cannot be undone.
                </span>
              </label>

              {error && (
                <p
                  role="alert"
                  className="rounded-lg border border-red-500/30 bg-red-500/5 px-3 py-2 text-sm text-red-400"
                >
                  {error}
                </p>
              )}

              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={closeDialog}
                  disabled={busy}
                  className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm font-medium text-[var(--foreground)] transition hover:bg-[var(--background)] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={busy || !password || !confirmed}
                  className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-red-500 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {busy ? "Deleting…" : "Permanently delete"}
                </button>
              </div>
            </form>
          </section>
        </div>
      )}
    </>
  );
}

function OrganizationPage({ organizations, onSelect, onCreate, onLogout }) {
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  function updateName(value) {
    setName(value);
    setSlug(
      value
        .toLowerCase()
        .trim()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "")
    );
  }

  async function createOrganization(event) {
    event.preventDefault();
    setError("");
    setBusy(true);

    try {
      await onCreate({ name: name.trim(), slug: slug.trim() });
    } catch (err) {
      setError(err.message || "Could not create the organization.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen flex items-center justify-center bg-[var(--background)] px-4">
      <section className="w-full max-w-xl rounded-xl border border-[var(--border)] bg-[var(--card)] p-6 sm:p-8">
        <div className="mb-6">
          <p className="text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)] mb-2">
            DocPilot workspace
          </p>
          <h1 className="text-2xl font-semibold tracking-tight text-[var(--foreground)] mb-2">
            Where would you like to work?
          </h1>
          <p className="text-sm leading-relaxed text-[var(--muted-foreground)]">
            Choose a workspace to access its documents and conversations.
          </p>
        </div>

        {organizations.length > 0 && (
          <div className="flex flex-col gap-3 mb-6">
            {organizations.map((organization) => (
              <button
                key={organization.id}
                type="button"
                onClick={() => onSelect(organization)}
                className="group w-full flex items-center gap-3 rounded-lg border border-[var(--border)] bg-[var(--background)] p-4 text-left hover:border-[var(--primary)] hover:bg-[var(--muted)] transition-colors"
              >
                <span className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--card)] text-lg" aria-hidden="true">
                  🏢
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-semibold text-[var(--foreground)]">
                    {organization.name}
                  </span>
                  <span className="block text-xs text-[var(--muted-foreground)] mt-1 truncate">
                    {organization.slug}
                  </span>
                </span>
                <span className="text-lg text-[var(--muted-foreground)] group-hover:text-[var(--foreground)]" aria-hidden="true">
                  →
                </span>
              </button>
            ))}
          </div>
        )}

        <div className="border-t border-[var(--border)] pt-5">
          {organizations.length === 0 ? (
            <>
              <div className="mb-4">
                <h2 className="text-base font-semibold text-[var(--foreground)] mb-1">
                  Create your first organization
                </h2>
                <p className="text-sm text-[var(--muted-foreground)]">
                  Your organization is the private workspace for your documents and conversations.
                </p>
              </div>

              <form onSubmit={createOrganization} className="flex flex-col gap-3">
                <div>
                  <label htmlFor="org-name" className="block text-xs mb-1.5 text-[var(--muted-foreground)]">
                    Organization name
                  </label>
                  <input
                    id="org-name"
                    required
                    maxLength={200}
                    value={name}
                    onChange={(event) => updateName(event.target.value)}
                    className="w-full rounded border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm text-[var(--foreground)]"
                    placeholder="e.g. My Organization"
                  />
                </div>

                <div>
                  <label htmlFor="org-slug" className="block text-xs mb-1.5 text-[var(--muted-foreground)]">
                    Organization slug
                  </label>
                  <input
                    id="org-slug"
                    required
                    pattern="[a-z0-9]+(-[a-z0-9]+)*"
                    maxLength={100}
                    value={slug}
                    onChange={(event) => setSlug(event.target.value)}
                    className="w-full rounded border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm text-[var(--foreground)]"
                    placeholder="e.g. my-organization"
                  />
                  <p className="mt-1 text-xs text-[var(--muted-foreground)]">
                    Lowercase letters, numbers, and hyphens only.
                  </p>
                </div>

                {error && (
                  <p role="alert" className="text-sm text-red-400">{error}</p>
                )}

                <button
                  type="submit"
                  disabled={busy || !name.trim() || !slug.trim()}
                  className="w-full rounded bg-[var(--primary)] px-3 py-2.5 text-sm font-medium text-[var(--primary-foreground)] hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {busy ? "Creating organization…" : "Create organization"}
                </button>
              </form>
            </>
          ) : (
            <details className="group">
              <summary className="flex cursor-pointer list-none items-center gap-3 rounded-lg p-3 hover:bg-[var(--muted)] transition-colors">
                <span className="flex h-9 w-9 items-center justify-center rounded-lg border border-[var(--border)] text-lg" aria-hidden="true">
                  +
                </span>
                <span className="flex-1">
                  <span className="block text-sm font-medium text-[var(--foreground)]">
                    Create an organization
                  </span>
                  <span className="block text-xs text-[var(--muted-foreground)] mt-1">
                    Set up a separate workspace
                  </span>
                </span>
                <span className="text-xs text-[var(--muted-foreground)] group-open:rotate-180 transition-transform" aria-hidden="true">
                  ▾
                </span>
              </summary>
              <div className="px-3 pt-3 pb-1">
                <p className="text-xs text-[var(--muted-foreground)] mb-4">
                  Each organization has its own documents, conversations, and workspace.
                </p>
          <form onSubmit={createOrganization} className="flex flex-col gap-3">
              <div>
                <label htmlFor="org-name" className="block text-xs mb-1.5 text-[var(--muted-foreground)]">
                  Organization name
                </label>
                <input
                  id="org-name"
                  required
                  value={name}
                  onChange={(event) => updateName(event.target.value)}
                  className="w-full rounded border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm text-[var(--foreground)]"
                />
              </div>
              <div>
                <label htmlFor="org-slug" className="block text-xs mb-1.5 text-[var(--muted-foreground)]">
                  Organization slug
                </label>
                <input
                  id="org-slug"
                  required
                  pattern="[a-z0-9]+(-[a-z0-9]+)*"
                  value={slug}
                  onChange={(event) => setSlug(event.target.value)}
                  className="w-full rounded border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm text-[var(--foreground)]"
                />
              </div>
              {error && <p role="alert" className="text-xs text-red-400">{error}</p>}
              <button
                type="submit"
                disabled={busy || !name.trim() || !slug.trim()}
                className="rounded bg-[var(--primary)] px-3 py-2 text-sm font-medium text-[var(--primary-foreground)] disabled:opacity-50"
              >
                {busy ? "Creating…" : "Create organization"}
              </button>
          </form>
              </div>
            </details>
          )}
        </div>

        {error && organizations.length > 0 && (
          <p role="alert" className="text-xs text-red-400 mb-3">{error}</p>
        )}

        <div className="mt-5 flex flex-wrap items-center gap-4">
          <DeleteAccountControl onDeleted={onLogout} />
          <button
            type="button"
            onClick={onLogout}
            className="text-xs text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
          >
            Sign out
          </button>
        </div>
      </section>
    </main>
  );
}

export default function App() {
  const [token, setToken] = useState(() => getAccessToken());
  const [user, setUser] = useState(null);
  const [organizations, setOrganizations] = useState([]);
  const [organization, setOrganization] = useState(null);
  const [page, setPage] = useState("chat");
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [conversations, setConversations] = useState([]);
  const [conversationsLoading, setConversationsLoading] = useState(false);
  const [deletingConversationId, setDeletingConversationId] = useState(null);
  const [conversationToDelete, setConversationToDelete] = useState(null);
  const [deleteConversationError, setDeleteConversationError] = useState("");
  const [loading, setLoading] = useState(Boolean(getAccessToken()));
  const [error, setError] = useState("");

  const loadConversations = useCallback(async (organizationId) => {
    if (!organizationId) {
      setConversations([]);
      setConversationsLoading(false);
      return;
    }

    setConversationsLoading(true);
    try {
      const result = await api.conversations(organizationId, { limit: 100 });
      setConversations(result.items || []);
    } catch (err) {
      console.error("Could not load conversations:", err);
      setConversations([]);
    } finally {
      setConversationsLoading(false);
    }
  }, []);

  const refreshConversations = useCallback(
    () => loadConversations(organization?.id),
    [loadConversations, organization?.id],
  );

  const selectConversation = useCallback((conversationId) => {
    setActiveConversationId(conversationId);
  }, []);

  const startNewChat = useCallback(() => {
    setActiveConversationId(null);
    setPage("chat");
  }, []);

  const deleteConversation = useCallback((conversation) => {
    setDeleteConversationError("");
    setConversationToDelete(conversation);
  }, []);

  const confirmDeleteConversation = useCallback(async () => {
    if (!conversationToDelete || deletingConversationId) return;

    const conversation = conversationToDelete;
    setDeletingConversationId(conversation.id);
    setDeleteConversationError("");

    try {
      await api.deleteConversation(organization?.id, conversation.id);
      setConversations((current) =>
        current.filter((item) => item.id !== conversation.id)
      );
      if (activeConversationId === conversation.id) {
        setActiveConversationId(null);
      }
      setConversationToDelete(null);
    } catch (err) {
      setDeleteConversationError(
        err.message || "Could not delete this conversation."
      );
    } finally {
      setDeletingConversationId(null);
    }
  }, [
    conversationToDelete,
    deletingConversationId,
    organization?.id,
    activeConversationId,
  ]);

  useEffect(() => {
    if (!conversationToDelete || deletingConversationId) return;

    function handleEscape(event) {
      if (event.key === "Escape") {
        setConversationToDelete(null);
        setDeleteConversationError("");
      }
    }

    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, [conversationToDelete, deletingConversationId]);

  useEffect(() => {
    setActiveConversationId(null);
    setConversations([]);
    if (organization?.id) {
      loadConversations(organization.id);
    }
  }, [organization?.id, loadConversations]);

  const loadWorkspace = useCallback(async () => {
    const [currentUser, organizationList] = await Promise.all([
      api.me(),
      api.organizations(),
    ]);

    setUser(currentUser);
    setOrganizations(organizationList);
    setOrganization((previous) => {
      if (previous) {
        return organizationList.find((item) => item.id === previous.id) || null;
      }
      return null;
    });
  }, []);

  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }

    let cancelled = false;

    async function initialize() {
      setLoading(true);
      setError("");

      try {
        const [currentUser, organizationList] = await Promise.all([
          api.me(),
          api.organizations(),
        ]);

        if (!cancelled) {
          setUser(currentUser);
          setOrganizations(organizationList);
        }
      } catch (err) {
        if (!cancelled) {
          clearAccessToken();
          setToken(null);
          setUser(null);
          setOrganizations([]);
          setOrganization(null);
          setError(err.message || "Please sign in again.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    initialize();

    return () => {
      cancelled = true;
    };
  }, [token]);

  async function login(email, password) {
    const result = await api.login(email, password);
    setAccessToken(result.access_token);
    setOrganization(null);
    setToken(result.access_token);
  }

  async function register(fullName, email, password) {
    await api.register(fullName, email, password);
    await login(email, password);
  }

  async function createOrganization(data) {
    const created = await api.createOrganization(data);
    await loadWorkspace();
    setOrganization(created);
  }

  function logout() {
    clearAccessToken();
    setToken(null);
    setUser(null);
    setOrganizations([]);
    setOrganization(null);
    setActiveConversationId(null);
    setConversations([]);
    setError("");
  }

  if (loading) {
    return (
      <main className="min-h-screen flex items-center justify-center bg-[var(--background)] text-sm text-[var(--muted-foreground)]">
        Loading your DocPilot workspace…
      </main>
    );
  }

  if (!token || !user) {
    return (
      <>
        {error && (
          <p className="text-xs text-red-400 text-center pt-3">{error}</p>
        )}
        <LoginPage onLogin={login} onRegister={register} />
      </>
    );
  }

  if (!organization) {
    return (
      <OrganizationPage
        organizations={organizations}
        onSelect={setOrganization}
        onCreate={createOrganization}
        onLogout={logout}
      />
    );
  }

  return (
    <AppShell
      currentPage={page}
      onNavigate={setPage}
      user={user}
      conversations={conversations}
      conversationsLoading={conversationsLoading}
      activeConversationId={activeConversationId}
      onConversationSelect={selectConversation}
      onNewChat={startNewChat}
      onConversationDelete={deleteConversation}
      deletingConversationId={deletingConversationId}
    >
      <div className="h-10 flex items-center justify-between gap-3 px-4 border-b border-[var(--border)] bg-[var(--card)]">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-xs text-[var(--muted-foreground)]">Workspace</span>
          <select
            aria-label="Select organization"
            value={organization.id}
            onChange={(event) => {
              const next = organizations.find((item) => item.id === event.target.value);
              setActiveConversationId(null);
              setOrganization(next || null);
            }}
            className="max-w-56 bg-transparent text-xs text-[var(--foreground)] border border-[var(--border)] rounded px-2 py-1"
          >
            {organizations.map((item) => (
              <option key={item.id} value={item.id}>{item.name}</option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-3 min-w-0">
          <span className="text-xs text-[var(--muted-foreground)] truncate">
            {user.full_name || user.email}
          </span>
          <DeleteAccountControl onDeleted={logout} />
          <button
            type="button"
            onClick={logout}
            className="text-xs text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
          >
            Sign out
          </button>
        </div>
      </div>

      {page === "chat" && (
        <ChatPage
          organizationId={organization.id}
          conversationId={activeConversationId}
          onConversationChange={setActiveConversationId}
          onConversationsChanged={refreshConversations}
        />
      )}
      {page === "eval" && <DashboardPage organizationId={organization.id} />}
      {page === "files" && <FileManagerPage organizationId={organization.id} />}
      {conversationToDelete && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
          onMouseDown={(event) => {
            if (
              event.target === event.currentTarget &&
              !deletingConversationId
            ) {
              setConversationToDelete(null);
              setDeleteConversationError("");
            }
          }}
        >
          <section
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="delete-conversation-title"
            aria-describedby="delete-conversation-description"
            className="w-full max-w-md rounded-xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-2xl"
          >
            <div className="mb-4 flex items-start gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-red-500/10 text-red-400">
                <svg
                  aria-hidden="true"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  className="h-5 w-5"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M12 9v4m0 4h.01M10.3 3.9 2.8 17a2 2 0 0 0 1.7 3h15a2 2 0 0 0 1.7-3l-7.5-13.1a2 2 0 0 0-3.4 0Z"
                  />
                </svg>
              </div>
              <div className="min-w-0 flex-1">
                <h2
                  id="delete-conversation-title"
                  className="text-base font-semibold text-[var(--foreground)]"
                >
                  Delete conversation?
                </h2>
                <p
                  id="delete-conversation-description"
                  className="mt-2 text-sm leading-6 text-[var(--muted-foreground)]"
                >
                  Permanently delete{" "}
                  <span className="break-words font-medium text-[var(--foreground)]">
                    “{conversationToDelete.title || "New conversation"}”
                  </span>{" "}
                  and all its messages? This action cannot be undone.
                </p>
              </div>
            </div>

            {deleteConversationError && (
              <p
                role="alert"
                className="mb-4 rounded-lg border border-red-500/30 bg-red-500/5 px-3 py-2 text-sm text-red-400"
              >
                {deleteConversationError}
              </p>
            )}

            <div className="mt-6 flex justify-end gap-3">
              <button
                type="button"
                disabled={Boolean(deletingConversationId)}
                onClick={() => {
                  setConversationToDelete(null);
                  setDeleteConversationError("");
                }}
                className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm font-medium text-[var(--foreground)] transition hover:bg-[var(--background)] disabled:cursor-not-allowed disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={Boolean(deletingConversationId)}
                onClick={confirmDeleteConversation}
                className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-red-500 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {deletingConversationId ? "Deleting…" : "Delete conversation"}
              </button>
            </div>
          </section>
        </div>
      )}
    </AppShell>
  );
}
