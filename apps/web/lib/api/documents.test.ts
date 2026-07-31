import { describe, expect, it, vi } from "vitest";

import {
  chunkDocumentVersion,
  embedDocumentVersion,
  extractDocumentVersion,
  listDocumentChunks,
  listDocumentVersions,
  listDocuments,
  transitionDocument,
  uploadDocument,
} from "./documents";
import type { DevelopmentDashboardSession } from "../auth/development-session";

const session: DevelopmentDashboardSession = {
  organisationId: "org-1",
  workspaceId: "workspace-1",
  userEmail: "admin@example.test",
  role: "client_admin",
};

function okResponse(data: unknown = { ok: true }) {
  return new Response(JSON.stringify({ success: true, data }), { status: 200 });
}

function fetchMock() {
  const mock = vi.fn().mockImplementation(() => Promise.resolve(okResponse([])));
  vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.local");
  vi.stubGlobal("fetch", mock);
  return mock;
}

describe("document dashboard API", () => {
  it("lists documents within the current workspace and organisation", async () => {
    const mock = fetchMock();

    await listDocuments(session);

    const [url, init] = mock.mock.calls[0];
    expect(String(url)).toBe("http://api.local/api/v1/workspaces/workspace-1/documents?organisation_id=org-1");
    expect(init.headers).toMatchObject({
      "X-Development-User-Email": "admin@example.test",
      "X-Development-Role": "client_admin",
    });
  });

  it("posts uploads as FormData without a JSON content type", async () => {
    const mock = fetchMock().mockResolvedValue(okResponse({ document: { id: "doc-1" }, document_version: { id: "ver-1" } }));
    const file = new File(["Admissions content"], "admissions.txt", { type: "text/plain" });

    await uploadDocument(session, { file, title: "Admissions", category: "policy" });

    const [url, init] = mock.mock.calls[0];
    expect(String(url)).toBe("http://api.local/api/v1/workspaces/workspace-1/documents/upload?organisation_id=org-1");
    expect(init.body).toBeInstanceOf(FormData);
    expect(init.headers).not.toHaveProperty("Content-Type");
  });

  it("uses existing version, chunk, extraction, chunking, embedding, and lifecycle endpoints", async () => {
    const mock = fetchMock();

    await listDocumentVersions(session, "doc-1");
    await listDocumentChunks(session, "doc-1", "ver-1");
    await extractDocumentVersion(session, "doc-1", "ver-1");
    await chunkDocumentVersion(session, "doc-1", "ver-1");
    await embedDocumentVersion(session, "doc-1", "ver-1");
    await transitionDocument(session, "doc-1", "archived");

    const urls = mock.mock.calls.map(([url]) => String(url));
    expect(urls).toContain("http://api.local/api/v1/workspaces/workspace-1/documents/doc-1/versions?organisation_id=org-1");
    expect(urls).toContain("http://api.local/api/v1/workspaces/workspace-1/documents/doc-1/versions/ver-1/chunks?organisation_id=org-1");
    expect(urls).toContain("http://api.local/api/v1/workspaces/workspace-1/documents/doc-1/versions/ver-1/extract?organisation_id=org-1");
    expect(urls).toContain("http://api.local/api/v1/workspaces/workspace-1/documents/doc-1/versions/ver-1/chunk?organisation_id=org-1");
    expect(urls).toContain("http://api.local/api/v1/workspaces/workspace-1/documents/doc-1/versions/ver-1/embed?organisation_id=org-1");
    expect(urls).toContain("http://api.local/api/v1/workspaces/workspace-1/documents/doc-1/transition?organisation_id=org-1");
  });
});
