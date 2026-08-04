"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";

import type { MembershipRecord } from "../../lib/api/users";
import { roleLabel } from "./role-badge";

export type PendingMemberAction =
  | { type: "role"; membership: MembershipRecord; role: string }
  | { type: "status"; membership: MembershipRecord; status: string }
  | null;

export function ConfirmActionDialog({
  action,
  pending,
  onCancel,
  onConfirm,
}: {
  action: PendingMemberAction;
  pending: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const reduceMotion = useReducedMotion();

  return (
    <AnimatePresence>
      {action ? (
        <motion.div
          className="dialogBackdrop"
          role="presentation"
          initial={reduceMotion ? false : { opacity: 0 }}
          animate={reduceMotion ? undefined : { opacity: 1 }}
          exit={reduceMotion ? undefined : { opacity: 0 }}
        >
          <motion.section
            className="confirmDialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="member-confirm-title"
            initial={reduceMotion ? false : { opacity: 0, y: 12, scale: 0.98 }}
            animate={reduceMotion ? undefined : { opacity: 1, y: 0, scale: 1 }}
            exit={reduceMotion ? undefined : { opacity: 0, y: 8, scale: 0.98 }}
          >
            <h2 id="member-confirm-title">{titleFor(action)}</h2>
            <p>{bodyFor(action)}</p>
            <p className="reviewFilterNote">Server-side RBAC remains authoritative regardless of this confirmation.</p>
            <div className="formActions">
              <button className="actionButton" type="button" onClick={onCancel} disabled={pending}>Cancel</button>
              <button className="actionButton" type="button" disabled={pending} onClick={onConfirm}>{pending ? "Saving" : "Confirm"}</button>
            </div>
          </motion.section>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

function titleFor(action: NonNullable<PendingMemberAction>) {
  if (action.type === "status") return action.status === "active" ? "Reactivate membership?" : "Deactivate membership?";
  return "Change role?";
}

function bodyFor(action: NonNullable<PendingMemberAction>) {
  if (action.type === "status") return `${action.membership.user.email} will be set to ${action.status}.`;
  return `${action.membership.user.email} will move from ${roleLabel(action.membership.role)} to ${roleLabel(action.role)}. This reduces their access.`;
}
