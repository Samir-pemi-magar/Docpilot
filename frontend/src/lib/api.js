const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api";

const TOKEN_KEY = "docpilot_access_token";

export function getAccessToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setAccessToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearAccessToken() {
  localStorage.removeItem(TOKEN_KEY);
}

async function request(path, options = {}) {
  const { preserveTokenOnUnauthorized = false, ...fetchOptions } = options;
  const token = getAccessToken();
  const headers = new Headers(fetchOptions.headers || {});

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  if (fetchOptions.body && !(fetchOptions.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...fetchOptions,
    headers,
  });

  if (response.status === 204) {
    return null;
  }

  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    if (response.status === 401 && !preserveTokenOnUnauthorized) {
      clearAccessToken();
    }

    const detail =
      typeof payload === "object" && payload !== null
        ? payload.detail
        : payload;

    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((item) => item.msg || JSON.stringify(item)).join("; ")
          : `Request failed (${response.status})`;

    throw new Error(message || `Request failed (${response.status})`);
  }

  return payload;
}

function jsonRequest(method, data) {
  return {
    method,
    body: JSON.stringify(data),
  };
}

export const api = {
  register(fullName, email, password) {
    return request(
      "/auth/register",
      jsonRequest("POST", {
        full_name: fullName,
        email,
        password,
      }),
    );
  },

  login(email, password) {
    return request("/auth/login", jsonRequest("POST", { email, password }));
  },

  me() {
    return request("/auth/me");
  },

  deleteAccount(password) {
    return request("/auth/me", {
      ...jsonRequest("DELETE", { password }),
      preserveTokenOnUnauthorized: true,
    });
  },

  organizations() {
    return request("/organizations");
  },

  createOrganization(data) {
    return request("/organizations", jsonRequest("POST", data));
  },

  organization(organizationId) {
    return request(`/organizations/${encodeURIComponent(organizationId)}`);
  },

  deleteOrganization(organizationId) {
    return request(
      `/organizations/${encodeURIComponent(organizationId)}`,
      { method: "DELETE" },
    );
  },

  conversations(organizationId, { limit = 20, offset = 0 } = {}) {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    return request(
      `/organizations/${encodeURIComponent(organizationId)}/conversations?${params}`,
    );
  },

  conversation(organizationId, conversationId) {
    return request(
      `/organizations/${encodeURIComponent(organizationId)}/conversations/${encodeURIComponent(conversationId)}`,
    );
  },

  deleteConversation(organizationId, conversationId) {
    return request(
      `/organizations/${encodeURIComponent(organizationId)}/conversations/${encodeURIComponent(conversationId)}`,
      { method: "DELETE" },
    );
  },

  chat(organizationId, query, conversationId = null, topK = 5) {
    return request(
      `/organizations/${encodeURIComponent(organizationId)}/chat`,
      jsonRequest("POST", {
        query,
        top_k: topK,
        ...(conversationId ? { conversation_id: conversationId } : {}),
      }),
    );
  },

  documents(organizationId) {
    return request(`/organizations/${encodeURIComponent(organizationId)}/documents`);
  },

  uploadDocument(organizationId, file, name = file.name) {
    const body = new FormData();
    body.append("name", name);
    body.append("file", file);

    return request(`/organizations/${encodeURIComponent(organizationId)}/documents`, {
      method: "POST",
      body,
    });
  },

  uploadDocumentVersion(organizationId, documentId, file) {
    const body = new FormData();
    body.append("file", file);

    return request(
      `/organizations/${encodeURIComponent(organizationId)}/documents/${encodeURIComponent(documentId)}/versions`,
      {
        method: "POST",
        body,
      },
    );
  },

  deleteDocument(organizationId, documentId) {
    return request(
      `/organizations/${encodeURIComponent(organizationId)}/documents/${encodeURIComponent(documentId)}`,
      { method: "DELETE" },
    );
  },

  evaluationDatasets(organizationId) {
    return request(`/organizations/${encodeURIComponent(organizationId)}/evaluation-datasets`);
  },
  createEvaluationDataset(organizationId, data) {
    return request(
      `/organizations/${encodeURIComponent(organizationId)}/evaluation-datasets`,
      jsonRequest("POST", data)
    );
  },
  evaluationCases(organizationId, datasetId) {
    return request(
      `/organizations/${encodeURIComponent(organizationId)}/evaluation-datasets/${encodeURIComponent(datasetId)}/cases`
    );
  },
  createEvaluationCase(organizationId, datasetId, data) {
    return request(
      `/organizations/${encodeURIComponent(organizationId)}/evaluation-datasets/${encodeURIComponent(datasetId)}/cases`,
      jsonRequest("POST", data)
    );
  },
  importEvaluationCases(
    organizationId,
    datasetId,
    content,
    documentIdMapping = {}
  ) {
    return request(
      `/organizations/${encodeURIComponent(organizationId)}/evaluation-datasets/${encodeURIComponent(datasetId)}/cases/import`,
      jsonRequest("POST", {
        content,
        document_id_mapping: documentIdMapping,
      })
    );
  },
  deleteEvaluationCase(organizationId, datasetId, caseId) {
    return request(
      `/organizations/${encodeURIComponent(organizationId)}/evaluation-datasets/${encodeURIComponent(datasetId)}/cases/${encodeURIComponent(caseId)}`,
      { method: "DELETE" }
    );
  },
  deleteAllEvaluationCases(organizationId, datasetId) {
    return request(
      `/organizations/${encodeURIComponent(organizationId)}/evaluation-datasets/${encodeURIComponent(datasetId)}/cases`,
      { method: "DELETE" }
    );
  },
  evaluationRuns(organizationId, limit = 20) {
    return request(
      `/organizations/${encodeURIComponent(organizationId)}/evaluation-datasets/runs?limit=${limit}`
    );
  },
  startEvaluationRun(organizationId, datasetId, topK = 5) {
    return request(
      `/organizations/${encodeURIComponent(organizationId)}/evaluation-datasets/${encodeURIComponent(datasetId)}/runs`,
      jsonRequest("POST", { top_k: topK })
    );
  },
  evaluationRun(organizationId, datasetId, runId) {
    return request(
      `/organizations/${encodeURIComponent(organizationId)}/evaluation-datasets/${encodeURIComponent(datasetId)}/runs/${encodeURIComponent(runId)}`
    );
  },
  evaluationRunResults(organizationId, datasetId, runId) {
    return request(
      `/organizations/${encodeURIComponent(organizationId)}/evaluation-datasets/${encodeURIComponent(datasetId)}/runs/${encodeURIComponent(runId)}/results?include_failures=true&limit=200`
    );
  },

};
