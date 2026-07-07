type PlaceholderPageProps = {
  eyebrow: string;
  title: string;
  description: string;
  primaryMetric: string;
  primaryMetricLabel: string;
  focusItems: string[];
};

export function PlaceholderPage({
  eyebrow,
  title,
  description,
  primaryMetric,
  primaryMetricLabel,
  focusItems,
}: PlaceholderPageProps) {
  return (
    <section className="pageStack" aria-labelledby="page-title">
      <div className="heroPanel">
        <div className="heroCopy">
          <p className="eyebrow">{eyebrow}</p>
          <h2 id="page-title">{title}</h2>
          <p>{description}</p>
        </div>
        <div className="metricTile" aria-label={`${primaryMetric}: ${primaryMetricLabel}`}>
          <strong>{primaryMetric}</strong>
          <span>{primaryMetricLabel}</span>
        </div>
      </div>

      <div className="contentGrid">
        <section className="focusPanel" aria-labelledby="focus-title">
          <p className="sectionKicker">Future focus</p>
          <h3 id="focus-title">What this page will make visible</h3>
          <ul>
            {focusItems.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>

        <section className="principlePanel" aria-labelledby="principle-title">
          <p className="sectionKicker">Operating rule</p>
          <h3 id="principle-title">Trust before automation</h3>
          <p>
            This foundation keeps the interface static until tenant isolation,
            permissions, source grounding, and data contracts are implemented.
          </p>
        </section>
      </div>
    </section>
  );
}
