import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LandingPage } from "../landing/landing-page";
import { LoginForm, OnboardingPanel, RegisterForm } from "./auth-forms";

const push = vi.fn();
const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh }),
  useSearchParams: () => new URLSearchParams("token=reset-token-12345678901234567890"),
}));

beforeEach(() => {
  push.mockReset();
  refresh.mockReset();
  vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.local");
});

describe("auth forms", () => {
  it("validates registration before submitting", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(<RegisterForm />);

    await userEvent.click(screen.getByRole("button", { name: /create account/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Enter your full name.");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("submits registration and redirects to onboarding", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      success: true,
      data: authContext(false),
      meta: {},
    }), { status: 201 })));
    render(<RegisterForm />);

    await userEvent.type(screen.getByLabelText("Full name"), "Ari Patel");
    await userEvent.type(screen.getByLabelText("Work email"), "ari@example.com");
    await userEvent.type(screen.getByLabelText("Organisation name"), "Acme");
    await userEvent.type(screen.getByLabelText("Password"), "SecurePass123");
    await userEvent.type(screen.getByLabelText("Confirm password"), "SecurePass123");
    await userEvent.click(screen.getByRole("button", { name: /create account/i }));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/onboarding"));
    expect(fetch).toHaveBeenCalledWith("http://api.local/api/v1/auth/register", expect.objectContaining({ credentials: "include" }));
  });

  it("shows duplicate registration errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "An account with this email already exists." }), { status: 409 })));
    render(<RegisterForm />);

    await userEvent.type(screen.getByLabelText("Full name"), "Ari Patel");
    await userEvent.type(screen.getByLabelText("Work email"), "ari@example.com");
    await userEvent.type(screen.getByLabelText("Organisation name"), "Acme");
    await userEvent.type(screen.getByLabelText("Password"), "SecurePass123");
    await userEvent.type(screen.getByLabelText("Confirm password"), "SecurePass123");
    await userEvent.click(screen.getByRole("button", { name: /create account/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("An account with this email already exists.");
  });

  it("submits login and handles invalid credentials", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({ detail: "Invalid email or password." }), { status: 401 })));
    render(<LoginForm />);

    await userEvent.type(screen.getByLabelText("Work email"), "ari@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "wrong");
    await userEvent.click(screen.getByRole("button", { name: /log in/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid email or password.");
  });

  it("completes onboarding and redirects to dashboard", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ success: true, data: authContext(true), meta: {} }), { status: 200 })));
    render(<OnboardingPanel />);

    await userEvent.click(screen.getByRole("button", { name: /continue to dashboard/i }));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/dashboard"));
  });
});

describe("landing auth links", () => {
  it("links primary CTAs to registration and login", () => {
    render(<LandingPage />);
    expect(screen.getAllByRole("link", { name: /get started free/i })[0].getAttribute("href")).toBe("/register");
    expect(screen.getByRole("link", { name: /log in/i }).getAttribute("href")).toBe("/login");
  });
});

function authContext(onboardingComplete: boolean) {
  return {
    user: { id: "user-1", email: "ari@example.com", full_name: "Ari Patel", status: "active", email_verified: false, onboarding_complete: onboardingComplete },
    organisation: { name: "Acme", slug: "acme", plan_key: "starter", status: "active" },
    workspace: { name: "Default workspace", slug: "default", status: "active" },
    membership: { role: "org_owner", status: "active" },
    organisation_id: "org-1",
    workspace_id: "workspace-1",
    role: "org_owner",
    onboarding_complete: onboardingComplete,
  };
}
