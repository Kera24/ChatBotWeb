import { AlertOctagon, FileSearch, Layers, MessageSquare, SearchX } from "lucide-react";
import Link from "next/link";

export function NoAssistantSelectedState() {
  return (
    <section className="conversationEmptyHero" role="status">
      <Layers size={30} aria-hidden="true" />
      <h2>No assistant selected</h2>
      <p>Select an assistant from My Assistants to review its conversation history.</p>
      <div className="conversationEmptyHeroActions">
        <Link className="assistantAction primary" href="/dashboard">Go to My Assistants</Link>
      </div>
    </section>
  );
}

export function NoConversationsState({ assistantId }: { assistantId: string }) {
  return (
    <section className="conversationEmptyHero" role="status">
      <MessageSquare size={30} aria-hidden="true" />
      <h2>No conversations have been recorded</h2>
      <p>Once this assistant is tested or deployed, conversations will appear here with messages and citations.</p>
      <div className="conversationEmptyHeroActions">
        <Link className="assistantAction primary" href={`/chatbot?assistant=${assistantId}`}>Open Chat Playground</Link>
        <Link className="assistantAction" href={`/knowledge?assistant=${assistantId}`}>Add knowledge</Link>
      </div>
    </section>
  );
}

export function NoFilterResultsState({ assistantId }: { assistantId: string }) {
  return (
    <section className="conversationEmptyHero" role="status">
      <SearchX size={30} aria-hidden="true" />
      <h2>No conversations match these filters</h2>
      <p>Try widening the date range or clearing the status and channel filters.</p>
      <div className="conversationEmptyHeroActions">
        <Link className="assistantAction primary" href={`/conversations?assistant=${assistantId}`}>Clear all filters</Link>
      </div>
    </section>
  );
}

export function ConversationNotFoundState({ assistantId }: { assistantId: string }) {
  return (
    <section className="conversationEmptyHero" role="status">
      <FileSearch size={30} aria-hidden="true" />
      <h2>Conversation not found</h2>
      <p>This conversation was not found in the current workspace. It may have been removed or the link may be incorrect.</p>
      <div className="conversationEmptyHeroActions">
        <Link className="assistantAction primary" href={`/conversations?assistant=${assistantId}`}>Back to conversations</Link>
      </div>
    </section>
  );
}

export function ConversationWrongAssistantState({ assistantId }: { assistantId: string }) {
  return (
    <section className="conversationEmptyHero" role="alert">
      <AlertOctagon size={30} aria-hidden="true" />
      <h2>This conversation belongs to a different assistant</h2>
      <p>The conversation you tried to open is not scoped to the currently selected assistant. Switch to the correct assistant to review it.</p>
      <div className="conversationEmptyHeroActions">
        <Link className="assistantAction primary" href={`/conversations?assistant=${assistantId}`}>Back to conversations</Link>
      </div>
    </section>
  );
}
