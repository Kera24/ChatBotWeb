import { FileSearch, Layers, SearchX, Sparkles } from "lucide-react";
import Link from "next/link";

export function NoAssistantSelectedState() {
  return (
    <section className="reviewEmptyHero" role="status">
      <Layers size={30} aria-hidden="true" />
      <h2>No assistant selected</h2>
      <p>Select an assistant from My Assistants to review its knowledge gaps.</p>
      <div className="reviewEmptyHeroActions">
        <Link className="assistantAction primary" href="/dashboard">Go to My Assistants</Link>
      </div>
    </section>
  );
}

export function NoReviewItemsState({ assistantId }: { assistantId: string }) {
  return (
    <section className="reviewEmptyHero" role="status">
      <Sparkles size={30} aria-hidden="true" />
      <h2>No flagged answers yet</h2>
      <p>Fallback, failed, and low-confidence answers will appear here for review once this assistant has been tested or used.</p>
      <div className="reviewEmptyHeroActions">
        <Link className="assistantAction primary" href={`/chatbot?assistant=${assistantId}`}>Open Chat Playground</Link>
        <Link className="assistantAction" href={`/knowledge?assistant=${assistantId}`}>Add knowledge</Link>
      </div>
    </section>
  );
}

export function NoFilterResultsState({ assistantId }: { assistantId: string }) {
  return (
    <section className="reviewEmptyHero" role="status">
      <SearchX size={30} aria-hidden="true" />
      <h2>No review items match these filters</h2>
      <p>Try widening the date range or clearing the answer-state, review-status, and channel filters.</p>
      <div className="reviewEmptyHeroActions">
        <Link className="assistantAction primary" href={`/review/unanswered?assistant=${assistantId}`}>Clear all filters</Link>
      </div>
    </section>
  );
}

export function ReviewItemNotFoundState({ assistantId }: { assistantId: string }) {
  return (
    <section className="reviewEmptyHero" role="status">
      <FileSearch size={30} aria-hidden="true" />
      <h2>Review item not found</h2>
      <p>This flagged answer was not found in the current workspace. It may have been removed or the link may be incorrect.</p>
      <div className="reviewEmptyHeroActions">
        <Link className="assistantAction primary" href={`/review/unanswered?assistant=${assistantId}`}>Back to review queue</Link>
      </div>
    </section>
  );
}
