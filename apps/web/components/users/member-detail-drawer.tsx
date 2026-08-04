"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { X } from "lucide-react";

import type { MembershipRecord } from "../../lib/api/users";
import { formatDate } from "./member-directory";
import { MemberStatusBadge } from "./member-status-badge";
import { roleDescription, roleLabel, RoleBadge } from "./role-badge";

type MemberDetailDrawerProps = {
  member: MembershipRecord | null;
  canManage: boolean;
  isCurrentUser: boolean;
  roles: string[];
  pending: boolean;
  onClose: () => void;
  onRequestRoleChange: (member: MembershipRecord, role: string) => void;
  onRequestStatusChange: (member: MembershipRecord, status: string) => void;
};

export function MemberDetailDrawer({ member, canManage, isCurrentUser, roles, pending, onClose, onRequestRoleChange, onRequestStatusChange }: MemberDetailDrawerProps) {
  const reduceMotion = useReducedMotion();

  return (
    <AnimatePresence>
      {member ? (
        <motion.div
          className="citationDrawerBackdrop memberDrawerBackdrop"
          role="presentation"
          initial={reduceMotion ? false : { opacity: 0 }}
          animate={reduceMotion ? undefined : { opacity: 1 }}
          exit={reduceMotion ? undefined : { opacity: 0 }}
          onClick={onClose}
        >
          <motion.aside
            className="citationDrawer memberDrawer"
            role="dialog"
            aria-modal="true"
            aria-labelledby="member-drawer-title"
            initial={reduceMotion ? false : { opacity: 0, x: 24 }}
            animate={reduceMotion ? undefined : { opacity: 1, x: 0 }}
            exit={reduceMotion ? undefined : { opacity: 0, x: 24 }}
            onClick={(event) => event.stopPropagation()}
          >
            <div className="citationDrawerHeader">
              <div>
                <p>Member profile</p>
                <h2 id="member-drawer-title">{member.user.full_name || member.user.email}</h2>
              </div>
              <button className="chatIconButton" type="button" onClick={onClose} aria-label="Close member details">
                <X size={18} aria-hidden="true" />
              </button>
            </div>

            <div className="memberDrawerBadges">
              <RoleBadge role={member.role} />
              <MemberStatusBadge status={member.status} />
              {isCurrentUser ? <span className="currentUserBadge">You</span> : null}
            </div>

            <dl className="citationFacts memberDrawerFacts">
              <div><dt>Email</dt><dd>{member.user.email}</dd></div>
              <div><dt>User status</dt><dd>{member.user.status}</dd></div>
              <div><dt>Membership status</dt><dd>{member.status}</dd></div>
              <div><dt>Role</dt><dd>{roleLabel(member.role)}</dd></div>
              <div><dt>Organisation</dt><dd>{member.organisation_name}</dd></div>
              <div><dt>Workspace</dt><dd>{member.workspace_name}</dd></div>
              <div><dt>Joined</dt><dd>{formatDate(member.created_at)}</dd></div>
              <div><dt>Last updated</dt><dd>{formatDate(member.updated_at)}</dd></div>
            </dl>

            <section className="memberPermissionSummary" aria-labelledby="member-permission-title">
              <p className="sectionKicker">Permissions summary</p>
              <h3 id="member-permission-title">What {roleLabel(member.role)} can do</h3>
              <p>{roleDescription(member.role)}</p>
            </section>

            {canManage ? (
              <section className="memberActionBar" aria-label="Membership actions">
                {isCurrentUser ? (
                  <p className="reviewFilterNote">You cannot change your own role or deactivate your own membership from this screen.</p>
                ) : (
                  <>
                    <label className="memberRoleField">
                      <span>Change role</span>
                      <select
                        aria-label={`Role for ${member.user.email}`}
                        value={member.role}
                        disabled={pending}
                        onChange={(event) => onRequestRoleChange(member, event.target.value)}
                      >
                        {roles.map((role) => <option value={role} key={role}>{roleLabel(role)}</option>)}
                      </select>
                    </label>
                    {member.status === "active" ? (
                      <button className="smallButton dangerButton" type="button" disabled={pending} onClick={() => onRequestStatusChange(member, "inactive")}>Deactivate</button>
                    ) : (
                      <button className="smallButton" type="button" disabled={pending} onClick={() => onRequestStatusChange(member, "active")}>Reactivate</button>
                    )}
                  </>
                )}
              </section>
            ) : (
              <p className="mutedText">Your role can view memberships but cannot change access.</p>
            )}
          </motion.aside>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
