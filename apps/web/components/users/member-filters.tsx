import { Search } from "lucide-react";

import { roleLabel } from "./role-badge";

export type MemberSortOption = "name-asc" | "role-desc" | "status-asc" | "joined-desc" | "joined-asc";

const SORT_LABELS: Record<MemberSortOption, string> = {
  "name-asc": "Name (A-Z)",
  "role-desc": "Role (highest first)",
  "status-asc": "Status",
  "joined-desc": "Joined (newest)",
  "joined-asc": "Joined (oldest)",
};

type MemberFiltersProps = {
  search: string;
  onSearchChange: (value: string) => void;
  roleFilter: string;
  onRoleFilterChange: (value: string) => void;
  statusFilter: string;
  onStatusFilterChange: (value: string) => void;
  sort: MemberSortOption;
  onSortChange: (value: MemberSortOption) => void;
  roles: string[];
  statuses: string[];
  onRefresh: () => void;
};

export function MemberFilters({
  search,
  onSearchChange,
  roleFilter,
  onRoleFilterChange,
  statusFilter,
  onStatusFilterChange,
  sort,
  onSortChange,
  roles,
  statuses,
  onRefresh,
}: MemberFiltersProps) {
  const activeFilters: Array<{ key: string; label: string; onClear: () => void }> = [];
  if (search) activeFilters.push({ key: "search", label: `Search: ${search}`, onClear: () => onSearchChange("") });
  if (roleFilter) activeFilters.push({ key: "role", label: `Role: ${roleLabel(roleFilter)}`, onClear: () => onRoleFilterChange("") });
  if (statusFilter) activeFilters.push({ key: "status", label: `Status: ${statusFilter}`, onClear: () => onStatusFilterChange("") });

  function clearAll() {
    onSearchChange("");
    onRoleFilterChange("");
    onStatusFilterChange("");
  }

  return (
    <div className="memberFilterBar">
      <form className="usersFilters premiumUsersControls" aria-label="Member filters" onSubmit={(event) => event.preventDefault()}>
        <label className="memberSearchField">
          <span>Search</span>
          <div className="memberSearchInput">
            <Search size={15} aria-hidden="true" />
            <input value={search} onChange={(event) => onSearchChange(event.target.value)} placeholder="Name, email, organisation, workspace" />
          </div>
        </label>
        <label>
          <span>Role</span>
          <select value={roleFilter} onChange={(event) => onRoleFilterChange(event.target.value)}>
            <option value="">All roles</option>
            {roles.map((role) => <option value={role} key={role}>{roleLabel(role)}</option>)}
          </select>
        </label>
        <label>
          <span>Status</span>
          <select value={statusFilter} onChange={(event) => onStatusFilterChange(event.target.value)}>
            <option value="">All statuses</option>
            {statuses.map((status) => <option value={status} key={status}>{status.replace(/_/g, " ")}</option>)}
          </select>
        </label>
        <label>
          <span>Sort</span>
          <select value={sort} onChange={(event) => onSortChange(event.target.value as MemberSortOption)}>
            {Object.entries(SORT_LABELS).map(([value, label]) => <option value={value} key={value}>{label}</option>)}
          </select>
        </label>
        <div className="memberFilterFormActions">
          <button className="smallButton" type="button" onClick={onRefresh}>Refresh</button>
          <button className="smallButton" type="button" onClick={clearAll} disabled={activeFilters.length === 0}>Clear all</button>
        </div>
      </form>

      {activeFilters.length > 0 ? (
        <ul className="memberActiveFilters" aria-label="Active member filters">
          {activeFilters.map((filter) => (
            <li key={filter.key}>
              <span>{filter.label}</span>
              <button type="button" onClick={filter.onClear} aria-label={`Remove filter: ${filter.label}`}>&times;</button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
