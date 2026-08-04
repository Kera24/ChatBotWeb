export function ReviewQueueSkeleton() {
  return (
    <section className="conversationPage reviewQueuePage premiumReviewQueuePage" aria-busy="true" aria-live="polite">
      <div className="premiumReviewHero reviewSkeletonBlock" />
      <div className="reviewMetricGrid" aria-hidden="true">
        {[0, 1, 2, 3].map((item) => <div className="reviewMetricCard reviewSkeletonBlock" key={item} />)}
      </div>
      <div className="premiumReviewControls reviewSkeletonBlock" />
      <div className="reviewList" aria-hidden="true">
        {[0, 1, 2, 3, 4].map((item) => <div className="reviewCard reviewSkeletonCard reviewSkeletonBlock" key={item} />)}
      </div>
    </section>
  );
}

export function ReviewDetailSkeleton() {
  return (
    <section className="reviewDetailPage premiumReviewDetailPage" aria-busy="true" aria-live="polite">
      <div className="premiumReviewDetailHero reviewSkeletonBlock" />
      <div className="reviewDetailGrid" aria-hidden="true">
        {[0, 1, 2, 3].map((item) => <div className="reviewStoryPanel reviewSkeletonBlock" key={item} />)}
      </div>
    </section>
  );
}
