import { Building2, Clock3, Mail } from "lucide-react";

import type { MembershipRecord } from "../../lib/api/users";
import { MemberAvatar } from "./member-avatar";
import { MemberStatusBadge } from "./member-status-badge";
import { RoleBadge } from "./role-badge";

export function MemberDirectory({
  members,
  selectedId,
  currentUserEmail,
  onSelect,
}: {
  members: MembershipRecord[];
  selectedId: string | null;
  currentUserEmail: string;
  onSelect: (membershipId: string) => void;
}) {
  return (
    <div className="memberDirectory" role="list" aria-label="Workspace members">
      {members.map((member) => (
        <MemberRow
          key={member.id}
          member={member}
          selected={member.id === selectedId}
          isCurrentUser={member.user.email.toLowerCase() === currentUserEmail.toLowerCase()}
          onSelect={onSelect}
        />
      ))}
    </div>
  );
}

export function MemberRow({
  member,
  selected,
  isCurrentUser,
  onSelect,
}: {
  member: MembershipRecord;
  selected: boolean;
  isCurrentUser: boolean;
  onSelect: (membershipId: string) => void;
}) {
  const name = member.user.full_name || "Unnamed user";
  return (
    <article className="memberRow" role="listitem">
      <button
        className={selected ? "memberRowButton selected" : "memberRowButton"}
        type="button"
        aria-pressed={selected}
        aria-label={`${name}, ${member.user.email}. ${member.role.replace(/_/g, " ")}, ${member.status}. View details.`}
        onClick={() => onSelect(member.id)}
      >
        <MemberAvatar name={member.user.full_name} email={member.user.email} />
        <div className="memberRowIdentity">
          <div className="memberRowNameLine">
            <strong>{name}</strong>
            {isCurrentUser ? <span className="currentUserBadge">You</span> : null}
          </div>
          <span className="memberRowEmail"><Mail size={12} aria-hidden="true" />{member.user.email}</span>
        </div>
        <div className="memberRowBadges">
          <RoleBadge role={member.role} />
          <MemberStatusBadge status={member.status} />
        </div>
        <div className="memberRowMeta" aria-hidden="true">
          <span><Building2 size={12} aria-hidden="true" />{member.workspace_name}</span>
          <span><Clock3 size={12} aria-hidden="true" />Joined {formatDate(member.created_at)}</span>
        </div>
      </button>
    </article>
  );
}

export function formatDate(value: string) {
  return new Intl.DateTimeFormat("en", { dateStyle: "medium" }).format(new Date(value));
}
