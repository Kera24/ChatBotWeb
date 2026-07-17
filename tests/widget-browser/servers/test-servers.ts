import { createServer, type IncomingMessage, type Server, type ServerResponse } from "node:http";
import { readFileSync, existsSync, statSync } from "node:fs";
import { extname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

export const HOST_ORIGIN = "http://127.0.0.1:4100";
export const WIDGET_ORIGIN = "http://127.0.0.1:4200";
export const API_ORIGIN = "http://127.0.0.1:4300";
export const WIDGET_KEY = "wpk_dev_1234567890abcdef";
export const DARK_WIDGET_KEY = "wpk_dev_darktheme0000000";
export const INVALID_COLOUR_WIDGET_KEY = "wpk_dev_invalidcolor0000";
export const FALLBACK_WIDGET_KEY = "wpk_dev_fallback00000000";
export const LOW_CONFIDENCE_WIDGET_KEY = "wpk_dev_lowconfidence000";
export const MALICIOUS_WIDGET_KEY = "wpk_dev_malicious0000000";
export const SLOW_WIDGET_KEY = "wpk_dev_slowmessage00000";
export const SESSION_TOKEN = "pss_dev_abcdefghijklmnop.abcdefghijklmnopqrstuvwx";

const repoRoot = resolve(fileURLToPath(new URL("../../../", import.meta.url)));
const sdkDist = join(repoRoot, "packages/widget-sdk/dist");
const widgetDist = join(repoRoot, "apps/widget/dist");

type RecordedRequest = {
  method: string;
  url: string;
  origin?: string;
  headers: Record<string, string | string[] | undefined>;
  body: string;
};

export type TestServers = Awaited<ReturnType<typeof startWidgetBrowserServers>>;

export async function startWidgetBrowserServers() {
  const apiRequests: RecordedRequest[] = [];
  const host = createServer((request, response) => handleHost(request, response));
  const widget = createServer((request, response) => handleWidget(request, response));
  const api = createServer((request, response) => handleApi(request, response, apiRequests));
  await Promise.all([
    listen(host, 4100),
    listen(widget, 4200),
    listen(api, 4300),
  ]);
  return {
    origins: { host: HOST_ORIGIN, widget: WIDGET_ORIGIN, api: API_ORIGIN },
    apiRequests,
    resetApiRequests: () => { apiRequests.length = 0; },
    close: async () => Promise.all([close(host), close(widget), close(api)]),
  };
}

function handleHost(request: IncomingMessage, response: ServerResponse): void {
  const url = new URL(request.url ?? "/", HOST_ORIGIN);
  if (url.pathname === "/normal" || url.pathname === "/") {
    html(response, hostPage({ mode: "normal", widgetKey: WIDGET_KEY }));
    return;
  }
  if (url.pathname === "/duplicate") {
    html(response, hostPage({ mode: "duplicate", widgetKey: WIDGET_KEY }));
    return;
  }
  if (url.pathname === "/csp") {
    response.setHeader("Content-Security-Policy", `default-src 'self'; script-src 'self' 'unsafe-inline' ${WIDGET_ORIGIN}; frame-src ${WIDGET_ORIGIN}; connect-src 'none'; style-src 'self' 'unsafe-inline'`);
    html(response, hostPage({ mode: "normal", widgetKey: WIDGET_KEY }));
    return;
  }
  if (url.pathname === "/dark") {
    html(response, hostPage({ mode: "normal", widgetKey: DARK_WIDGET_KEY }));
    return;
  }
  if (url.pathname === "/invalid-colour") {
    html(response, hostPage({ mode: "normal", widgetKey: INVALID_COLOUR_WIDGET_KEY }));
    return;
  }
  if (url.pathname === "/fallback") { html(response, hostPage({ mode: "normal", widgetKey: FALLBACK_WIDGET_KEY })); return; }
  if (url.pathname === "/low-confidence") { html(response, hostPage({ mode: "normal", widgetKey: LOW_CONFIDENCE_WIDGET_KEY })); return; }
  if (url.pathname === "/malicious") { html(response, hostPage({ mode: "normal", widgetKey: MALICIOUS_WIDGET_KEY })); return; }
  if (url.pathname === "/slow") { html(response, hostPage({ mode: "normal", widgetKey: SLOW_WIDGET_KEY })); return; }
  if (url.pathname === "/blocked-frame") {
    response.setHeader("Content-Security-Policy", `default-src 'self'; script-src 'self' 'unsafe-inline' ${WIDGET_ORIGIN}; frame-src 'none'; style-src 'self' 'unsafe-inline'`);
    html(response, hostPage({ mode: "normal", widgetKey: WIDGET_KEY }));
    return;
  }
  text(response, 404, "not found");
}

function hostPage(options: { mode: "normal" | "duplicate"; widgetKey: string }): string {
  const duplicate = options.mode === "duplicate" ? "window.YoranixWidget.init(config).catch((error) => { window.__secondInitError = error; });" : "";
  return `<!doctype html>
<html>
<head><meta charset="utf-8"><title>Widget host test</title></head>
<body>
<button id="before-widget">Before widget</button>
<button id="host-click-target" onclick="window.__hostClicked = true">Host target</button>
<script src="${WIDGET_ORIGIN}/sdk/yoranix-widget-sdk.global.js"></script>
<script>
window.__widgetEvents = [];
const config = { widgetKey: "${options.widgetKey}", environment: "development", iframeHost: "${WIDGET_ORIGIN}" };
window.YoranixWidget.on('ready', (event) => window.__widgetEvents.push(['ready', event]));
window.YoranixWidget.on('opened', (event) => window.__widgetEvents.push(['opened', event]));
window.YoranixWidget.on('closed', (event) => window.__widgetEvents.push(['closed', event]));
window.__readyPromise = window.YoranixWidget.init(config).catch((error) => { window.__initError = error; throw error; });
${duplicate}
</script>
</body>
</html>`;
}

function handleWidget(request: IncomingMessage, response: ServerResponse): void {
  const url = new URL(request.url ?? "/", WIDGET_ORIGIN);
  if (url.pathname === "/sdk/yoranix-widget-sdk.global.js") {
    file(response, join(sdkDist, "yoranix-widget-sdk.global.js"));
    return;
  }
  if (url.pathname.startsWith("/assets/")) {
    file(response, join(widgetDist, url.pathname));
    return;
  }
  if (url.pathname.startsWith("/embed/")) {
    file(response, join(widgetDist, "index.html"));
    return;
  }
  text(response, 404, "not found");
}

function handleApi(request: IncomingMessage, response: ServerResponse, requests: RecordedRequest[]): void {
  const url = new URL(request.url ?? "/", API_ORIGIN);
  const origin = request.headers.origin;
  if (origin === WIDGET_ORIGIN) {
    response.setHeader("Access-Control-Allow-Origin", origin);
    response.setHeader("Vary", "Origin");
    response.setHeader("Access-Control-Allow-Credentials", "false");
  }
  if (request.method === "OPTIONS") {
    response.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
    response.setHeader("Access-Control-Allow-Headers", url.pathname.endsWith("/messages") ? "Content-Type, Idempotency-Key" : "Content-Type");
    response.writeHead(origin === WIDGET_ORIGIN ? 204 : 403);
    response.end();
    return;
  }
  let body = "";
  request.on("data", (chunk) => { body += String(chunk); });
  request.on("end", () => {
    requests.push({ method: request.method ?? "GET", url: url.pathname + url.search, origin, headers: request.headers, body });
    const scenario = url.searchParams.get("scenario");
    if (origin !== WIDGET_ORIGIN || scenario === "origin-denied") {
      json(response, 403, { code: "origin_not_allowed", message: "Origin denied", retryable: false });
      return;
    }
    if (url.pathname.endsWith("/config")) {
      if (request.headers["if-none-match"] === '"cfg-1"') {
        response.setHeader("ETag", '"cfg-1"');
        response.writeHead(304);
        response.end();
        return;
      }
      response.setHeader("ETag", '"cfg-1"');
      json(response, 200, configResponse(url.pathname));
      return;
    }
    if (url.pathname.endsWith("/sessions")) {
      if (scenario === "rate-limited") {
        response.setHeader("Retry-After", "5");
        json(response, 429, { code: "rate_limited", message: "Slow down", retryable: true, retry_after_seconds: 5 });
        return;
      }
      json(response, 200, sessionResponse());
      return;
    }
    if (url.pathname.endsWith("/messages")) {
      if (scenario === "invalid-session") {
        json(response, 404, { code: "invalid_session", message: "Invalid session", retryable: false });
        return;
      }
      const payload = messageResponse(url.pathname);
      if (url.pathname.includes(SLOW_WIDGET_KEY)) {
        setTimeout(() => json(response, 200, payload), 160);
        return;
      }
      json(response, 200, payload);
      return;
    }
    json(response, 404, { code: "invalid_widget", message: "Widget unavailable", retryable: false });
  });
}

function configResponse(pathname: string) {
  const isDark = pathname.includes(DARK_WIDGET_KEY);
  const isInvalidColour = pathname.includes(INVALID_COLOUR_WIDGET_KEY);
  return {
    widget: { bot_name: "Yoranix", welcome_message: "Hello", launcher_label: "Chat", primary_colour: isInvalidColour ? "not-a-colour" : "#123456", secondary_colour: null, logo_url: null, avatar_url: null, position: "bottom-right", theme_mode: isDark ? "dark" : "light", language: "en" },
    behaviour: { suggested_questions: ["What can you do?"], max_initial_suggestions: 1, show_citations: true, allow_conversation_history: false, session_required: true, messages_enabled: true },
    privacy: { privacy_notice_text: null, privacy_notice_url: null, terms_url: null, fallback_contact_text: null },
    capabilities: { can_create_session: true, can_send_messages: true, citations_enabled: true, conversation_history_enabled: false },
    configuration_version: 1,
    response_schema_version: "1.0",
    published_at: "2026-07-16T00:00:00.000Z",
    request_id: "req_config",
  };
}

function sessionResponse() {
  return {
    session_token: SESSION_TOKEN,
    expires_at: "2099-07-16T01:00:00.000Z",
    absolute_expires_at: "2099-07-16T02:00:00.000Z",
    inactivity_timeout_seconds: 1800,
    max_messages: 20,
    remaining_messages: 19,
    configuration_version: 1,
    capabilities: { can_send_messages: true, conversation_history_enabled: false, citations_enabled: true },
    request_id: "req_session",
  };
}

function messageResponse(pathname: string) {
  if (pathname.includes(FALLBACK_WIDGET_KEY)) {
    return { response_id: "resp_fallback", answer: "I could not find this in the available information.", answer_state: "fallback", citations: [], remaining_messages: 18, session_expires_at: "2099-07-16T01:10:00.000Z", fallback_used: true, request_id: "req_message", response_schema_version: "1.0" };
  }
  if (pathname.includes(LOW_CONFIDENCE_WIDGET_KEY)) {
    return { response_id: "resp_low", answer: "This may help, but please verify it against the available sources.", answer_state: "low_confidence", citations: [], remaining_messages: 18, session_expires_at: "2099-07-16T01:10:00.000Z", fallback_used: false, request_id: "req_message", response_schema_version: "1.0" };
  }
  if (pathname.includes(MALICIOUS_WIDGET_KEY)) {
    return { response_id: "resp_malicious", answer: "<script>alert(1)</script>\n<img src=x onerror=alert(1)>\n[a](javascript:alert(1))", answer_state: "answered", citations: [], remaining_messages: 18, session_expires_at: "2099-07-16T01:10:00.000Z", fallback_used: false, request_id: "req_message", response_schema_version: "1.0" };
  }
  return {
    response_id: "resp_1",
    answer: "Safe answer",
    answer_state: "answered",
    citations: [],
    remaining_messages: 18,
    session_expires_at: "2099-07-16T01:10:00.000Z",
    fallback_used: false,
    request_id: "req_message",
    response_schema_version: "1.0",
  };
}
function file(response: ServerResponse, path: string): void {
  if (!existsSync(path) || !statSync(path).isFile()) {
    text(response, 404, `missing ${path}`);
    return;
  }
  response.setHeader("Content-Type", contentType(path));
  response.end(readFileSync(path));
}

function html(response: ServerResponse, body: string): void {
  response.setHeader("Content-Type", "text/html; charset=utf-8");
  response.end(body);
}

function json(response: ServerResponse, status: number, body: unknown): void {
  response.setHeader("Content-Type", "application/json");
  response.writeHead(status);
  response.end(JSON.stringify(body));
}

function text(response: ServerResponse, status: number, body: string): void {
  response.writeHead(status, { "Content-Type": "text/plain; charset=utf-8" });
  response.end(body);
}

function contentType(path: string): string {
  const ext = extname(path);
  if (ext === ".js") return "application/javascript";
  if (ext === ".css") return "text/css";
  if (ext === ".html") return "text/html; charset=utf-8";
  return "application/octet-stream";
}

function listen(server: Server, port: number): Promise<void> {
  return new Promise((resolveListen) => server.listen(port, "127.0.0.1", () => resolveListen()));
}

function close(server: Server): Promise<void> {
  return new Promise((resolveClose, reject) => server.close((error) => error ? reject(error) : resolveClose()));
}
