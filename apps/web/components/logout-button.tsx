"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { logoutAccount } from "../lib/api/auth";

export function LogoutButton() {
  const router = useRouter();
  const [pending, setPending] = useState(false);

  async function logout() {
    setPending(true);
    try {
      await logoutAccount();
      router.push("/login");
      router.refresh();
    } finally {
      setPending(false);
    }
  }

  return <button className="logoutButton" type="button" disabled={pending} onClick={logout}>{pending ? "Signing out" : "Log out"}</button>;
}
