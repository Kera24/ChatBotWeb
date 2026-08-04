import { Plus, Sparkles } from "lucide-react";
import Link from "next/link";

export function ZeroAssistantState() {
  return (
    <section className="overviewEmptyHero" role="status">
      <Sparkles size={30} aria-hidden="true" />
      <h2>Create your first assistant</h2>
      <p>Your workspace is ready, but no assistants have been created yet. Create an assistant, add knowledge, and publish a widget to start answering customer questions.</p>
      <div className="overviewEmptyHeroActions">
        <Link className="assistantAction primary" href="/assistants/new"><Plus size={15} aria-hidden="true" />Create assistant</Link>
      </div>
    </section>
  );
}
