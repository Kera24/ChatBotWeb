export function OverviewSkeleton() {
  return (
    <section className="overviewPage premiumOverviewPage" aria-busy="true" aria-live="polite">
      <div className="premiumOverviewHero overviewSkeletonBlock">
        <div>
          <p className="eyebrow">Loading</p>
          <h2>Loading Conversa overview</h2>
          <p>Collecting tenant-scoped dashboard signals.</p>
        </div>
      </div>
      <div className="overviewMetricGrid" aria-hidden="true">
        {[0, 1, 2, 3, 4, 5].map((item) => <div className="overviewMetricCard overviewSkeletonBlock" key={item} />)}
      </div>
      <div className="overviewLayout" aria-hidden="true">
        <div className="overviewPanel overviewSkeletonBlock" />
        <div className="overviewPanel overviewSkeletonBlock" />
      </div>
    </section>
  );
}
