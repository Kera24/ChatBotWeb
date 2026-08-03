"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Bot, Check, ChevronDown, Plus } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { getDashboardApiBaseUrl } from "../../lib/api/client";
import type { ApiEnvelope } from "../../lib/api/types";
import type { WidgetSummary } from "../../lib/api/widgets";
import type { AuthContext } from "../../lib/auth/development-session";
import { assistantLifecycle, AssistantStatusBadge } from "./assistant-management";

type SwitcherState = {
  loading: boolean;
  open: boolean;
  assistants: WidgetSummary[];
  selectedId: string | null;
  error: string | null;
  workspaceId: string | null;
};

export function AssistantSwitcher() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const reduceMotion = useReducedMotion();
  const containerRef = useRef<HTMLDivElement>(null);
  const [state, setState] = useState<SwitcherState>({ loading: true, open: false, assistants: [], selectedId: null, error: null, workspaceId: null });

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const authResponse = await fetch(`${getDashboardApiBaseUrl()}/api/v1/auth/me`, { credentials: "include", headers: { Accept: "application/json" } });
        if (!authResponse.ok) throw new Error("Authentication is required.");
        const authPayload = (await authResponse.json()) as ApiEnvelope<AuthContext>;
        const context = authPayload.data;
        const widgetResponse = await fetch(`${getDashboardApiBaseUrl()}/api/v1/workspaces/${context.workspace_id}/widgets?organisation_id=${context.organisation_id}`, { credentials: "include", headers: { Accept: "application/json" } });
        if (!widgetResponse.ok) throw new Error("Assistants could not be loaded.");
        const widgetPayload = (await widgetResponse.json()) as ApiEnvelope<WidgetSummary[]>;
        if (cancelled) return;
        const storageKey = selectedStorageKey(context.workspace_id);
        const urlSelected = searchParams.get("assistant");
        const storedSelected = typeof window !== "undefined" ? window.localStorage.getItem(storageKey) : null;
        const selectedId = firstExistingId(widgetPayload.data, urlSelected) ?? firstExistingId(widgetPayload.data, storedSelected) ?? widgetPayload.data[0]?.id ?? null;
        setState({ loading: false, open: false, assistants: widgetPayload.data, selectedId, error: null, workspaceId: context.workspace_id });
        if (!urlSelected && selectedId && requiresAssistantContext(pathname)) {
          const params = new URLSearchParams(searchParams.toString());
          params.set("assistant", selectedId);
          router.replace(`${pathname}?${params.toString()}`);
        }
      } catch (error) {
        if (!cancelled) setState((current) => ({ ...current, loading: false, error: error instanceof Error ? error.message : "Assistants could not be loaded." }));
      }
    }
    load();
    return () => { cancelled = true; };
  }, [pathname, router, searchParams]);

  useEffect(() => {
    function onDocumentClick(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setState((current) => ({ ...current, open: false }));
      }
    }
    document.addEventListener("mousedown", onDocumentClick);
    return () => document.removeEventListener("mousedown", onDocumentClick);
  }, []);

  const selected = useMemo(() => state.assistants.find((assistant) => assistant.id === state.selectedId) ?? null, [state.assistants, state.selectedId]);

  function selectAssistant(assistant: WidgetSummary) {
    if (state.workspaceId && typeof window !== "undefined") window.localStorage.setItem(selectedStorageKey(state.workspaceId), assistant.id);
    setState((current) => ({ ...current, selectedId: assistant.id, open: false }));
    const params = new URLSearchParams(searchParams.toString());
    params.set("assistant", assistant.id);
    if (pathname.startsWith("/assistants/") && pathname !== "/assistants/new") {
      router.push(`/assistants/${assistant.id}`);
      return;
    }
    router.replace(`${pathname}?${params.toString()}`);
  }

  if (pathname === "/" || pathname.startsWith("/login") || pathname.startsWith("/register") || pathname.startsWith("/forgot-password") || pathname.startsWith("/reset-password") || pathname.startsWith("/verify-email") || pathname.startsWith("/onboarding")) {
    return null;
  }

  return (
    <div className="assistantSwitcher" ref={containerRef}>
      <button
        className="assistantSwitcherButton"
        type="button"
        aria-haspopup="menu"
        aria-expanded={state.open}
        onClick={() => setState((current) => ({ ...current, open: !current.open }))}
        disabled={state.loading || Boolean(state.error)}
      >
        <Bot size={17} aria-hidden="true" />
        <span>{state.loading ? "Loading assistants" : selected?.display_name ?? "No assistant selected"}</span>
        <ChevronDown size={16} aria-hidden="true" />
      </button>
      <AnimatePresence>
        {state.open ? (
          <motion.div
            className="assistantSwitcherMenu"
            role="menu"
            initial={reduceMotion ? false : { opacity: 0, y: -6, scale: 0.98 }}
            animate={reduceMotion ? undefined : { opacity: 1, y: 0, scale: 1 }}
            exit={reduceMotion ? undefined : { opacity: 0, y: -6, scale: 0.98 }}
            transition={{ duration: 0.16 }}
          >
            {state.assistants.length === 0 ? <p className="assistantSwitcherEmpty">No assistants yet</p> : null}
            {state.assistants.map((assistant) => (
              <button className="assistantSwitcherItem" type="button" role="menuitem" key={assistant.id} onClick={() => selectAssistant(assistant)}>
                <span><strong>{assistant.display_name}</strong><AssistantStatusBadge status={assistantLifecycle(assistant)} /></span>
                {assistant.id === state.selectedId ? <Check size={16} aria-hidden="true" /> : null}
              </button>
            ))}
            <Link className="assistantSwitcherCreate" href="/assistants/new" role="menuitem"><Plus size={16} aria-hidden="true" />Create Assistant</Link>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}

function selectedStorageKey(workspaceId: string) {
  return `yoranix:selected-assistant:${workspaceId}`;
}

function firstExistingId(assistants: WidgetSummary[], candidate: string | null) {
  if (!candidate) return null;
  return assistants.some((assistant) => assistant.id === candidate) ? candidate : null;
}

function requiresAssistantContext(pathname: string) {
  return pathname === "/knowledge" || pathname === "/chatbot" || pathname === "/analytics" || pathname === "/conversations" || pathname.startsWith("/conversations/") || pathname === "/review/unanswered" || pathname.startsWith("/review/unanswered/");
}
