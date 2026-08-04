export function UsersSkeleton() {
  return (
    <section className="usersPage premiumUsersPage" aria-busy="true" aria-live="polite">
      <div className="premiumUsersHero usersSkeletonBlock">
        <div>
          <p className="eyebrow">Loading</p>
          <h2>Loading Conversa users</h2>
          <p>Collecting tenant-scoped membership records.</p>
        </div>
      </div>
      <div className="usersMetricGrid" aria-hidden="true">
        {[0, 1, 2, 3, 4, 5].map((item) => <div className="usersMetricCard usersSkeletonBlock" key={item} />)}
      </div>
      <div className="premiumUsersControls usersSkeletonBlock" />
      <div className="memberDirectory" aria-hidden="true">
        {[0, 1, 2, 3].map((item) => <div className="memberRow memberSkeletonRow usersSkeletonBlock" key={item} />)}
      </div>
    </section>
  );
}
