export function MemberAvatar({ name, email }: { name: string | null; email: string }) {
  const initials = initialsFor(name, email);
  return (
    <span className="memberAvatar" aria-hidden="true">
      {initials}
    </span>
  );
}

export function initialsFor(name: string | null, email: string) {
  const source = (name ?? "").trim();
  if (source) {
    const parts = source.split(/\s+/).filter(Boolean);
    if (parts.length >= 2) return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
    return source.slice(0, 2).toUpperCase();
  }
  return email.slice(0, 2).toUpperCase();
}
