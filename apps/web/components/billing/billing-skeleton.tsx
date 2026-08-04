export function BillingSkeleton() {
  return (
    <section className="settingsPage premiumSettingsPage" aria-busy="true" aria-live="polite">
      <div className="premiumSettingsHero settingsSkeletonBlock">
        <div>
          <p className="eyebrow">Loading</p>
          <h2>Loading Conversa billing</h2>
          <p>Collecting subscription, plan, and invoice data.</p>
        </div>
      </div>
      <div className="settingsMetricGrid" aria-hidden="true">
        {[0, 1, 2, 3].map((item) => (
          <div className="settingsMetricCard settingsSkeletonBlock" key={item} />
        ))}
      </div>
      <div className="settingsLayout" aria-hidden="true">
        <div className="settingsPanel settingsSkeletonBlock" />
        <div className="settingsPanel settingsSkeletonBlock" />
      </div>
    </section>
  );
}
