import { Eye, SearchX, Users as UsersIcon } from "lucide-react";

export function NoMembersState() {
  return (
    <div className="usersEmptyState premiumEmptyState" role="status">
      <UsersIcon size={26} aria-hidden="true" />
      <h4>No members yet</h4>
      <p>Organisation memberships will appear here once members are added to this workspace.</p>
    </div>
  );
}

export function NoResultsState({ onClear }: { onClear: () => void }) {
  return (
    <div className="usersEmptyState premiumEmptyState" role="status">
      <SearchX size={26} aria-hidden="true" />
      <h4>No matching members</h4>
      <p>Adjust search, role, or status filters.</p>
      <button className="smallButton" type="button" onClick={onClear}>Clear all filters</button>
    </div>
  );
}

export function NoMemberSelectedState() {
  return (
    <div className="usersEmptyState premiumEmptyState" role="status">
      <UsersIcon size={26} aria-hidden="true" />
      <h4>No member selected</h4>
      <p>Select a member to inspect details.</p>
    </div>
  );
}

export function ReadOnlyNotice() {
  return (
    <p className="usersReadOnlyNotice" role="status">
      <Eye size={15} aria-hidden="true" />
      Your role can view memberships but cannot change roles or access.
    </p>
  );
}
