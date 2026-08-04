export function ConversationsListSkeleton() {
  return (
    <section className="conversationPage premiumConversationsPage" aria-busy="true" aria-live="polite">
      <div className="premiumConversationsHero conversationSkeletonBlock" />
      <div className="premiumConversationControls conversationSkeletonBlock" />
      <div className="conversationInbox" aria-hidden="true">
        {[0, 1, 2, 3, 4].map((item) => (
          <div className="conversationCard conversationSkeletonCard conversationSkeletonBlock" key={item} />
        ))}
      </div>
    </section>
  );
}

export function ConversationDetailSkeleton() {
  return (
    <section className="conversationDetailPage premiumConversationDetailPage" aria-busy="true" aria-live="polite">
      <div className="premiumConversationDetailHero conversationSkeletonBlock" />
      <div className="conversationDetailGrid">
        <div className="premiumTranscript conversationSkeletonTranscript" aria-hidden="true">
          {[0, 1, 2].map((item) => (
            <div className="chatBubble assistantBubble conversationSkeletonBlock" key={item} />
          ))}
        </div>
        <div className="conversationQualityPanel conversationSkeletonBlock" />
      </div>
    </section>
  );
}
