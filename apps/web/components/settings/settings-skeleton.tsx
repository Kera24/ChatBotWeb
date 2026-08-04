export function SettingsSkeleton() {
  return (
    <section className="settingsPage premiumSettingsPage" aria-busy="true" aria-live="polite">
      <div className="premiumSettingsHero settingsSkeletonBlock">
        <div>
          <p className="eyebrow">Loading</p>
          <h2>Loading Conversa settings</h2>
          <p>Collecting tenant-scoped workspace and operational configuration.</p>
        </div>
      </div>
      <div className="settingsMetricGrid" aria-hidden="true">
        {[0, 1, 2, 3, 4].map((item) => <div className="settingsMetricCard settingsSkeletonBlock" key={item} />)}
      </div>
      <div className="settingsLayout" aria-hidden="true">
        <div className="settingsPanel settingsSkeletonBlock" />
        <div className="settingsPanel settingsSkeletonBlock" />
      </div>
    </section>
  );
}
