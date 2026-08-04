import { FileText, MessageSquare, PlusCircle, Rocket, Settings, ShieldAlert, Users as UsersIcon } from "lucide-react";
import Link from "next/link";

export function QuickActions({ primaryAssistantId }: { primaryAssistantId: string | null }) {
  const actions = [
    { key: "create", label: "Create assistant", href: "/assistants/new", icon: PlusCircle },
    ...(primaryAssistantId
      ? [
          { key: "knowledge", label: "Upload knowledge", href: `/knowledge?assistant=${primaryAssistantId}`, icon: FileText },
          { key: "playground", label: "Test assistant", href: `/assistants/${primaryAssistantId}?tab=playground&assistant=${primaryAssistantId}`, icon: MessageSquare },
          { key: "widget", label: "Configure widget", href: `/assistants/${primaryAssistantId}?tab=widget&assistant=${primaryAssistantId}`, icon: Rocket },
          { key: "conversations", label: "Review conversations", href: `/conversations?assistant=${primaryAssistantId}`, icon: MessageSquare },
          { key: "review", label: "Resolve knowledge gaps", href: `/review/unanswered?assistant=${primaryAssistantId}`, icon: ShieldAlert },
        ]
      : []),
    { key: "team", label: "Manage team", href: "/users", icon: UsersIcon },
    { key: "settings", label: "Open settings", href: "/settings", icon: Settings },
  ];

  return (
    <section className="overviewQuickActions" aria-labelledby="quick-actions-title">
      <div>
        <p className="sectionKicker">Quick actions</p>
        <h3 id="quick-actions-title">Move to the right operational surface</h3>
      </div>
      <div className="overviewActionList">
        {actions.map((action) => (
          <Link className="actionButton" href={action.href} key={action.key}>
            <action.icon size={15} aria-hidden="true" />
            {action.label}
          </Link>
        ))}
      </div>
    </section>
  );
}
