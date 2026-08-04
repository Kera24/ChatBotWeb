import { ArrowRight } from "lucide-react";
import Link from "next/link";

import type { OverviewData } from "../../lib/api/overview";

export function QualitySummary({ data, recentWindowLimit }: { data: OverviewData; recentWindowLimit: number }) {
  const withCitations = data.reviewItems.filter((item) => item.citation_count > 0).length;
  const latencies = data.reviewItems.map((item) => item.latency_ms).filter((value): value is number => typeof value === "number");
  const averageLatency = latencies.length === 0 ? null : Math.round(latencies.reduce((sum, value) => sum + value, 0) / latencies.length);
  const stateCounts = {
    fallback: data.reviewItems.filter((item) => item.answer_state === "fallback").length,
    low_confidence: data.reviewItems.filter((item) => item.answer_state === "low_confidence").length,
    failed: data.reviewItems.filter((item) => item.answer_state === "failed").length,
  };

  return (
    <section className="overviewPanel qualitySummaryPanel" aria-labelledby="quality-title">
      <div className="overviewPanelHeader">
        <div>
          <p className="sectionKicker">Conversation &amp; quality</p>
          <h3 id="quality-title">Recent signal</h3>
        </div>
        <Link className="smallButton" href="/conversations">Open conversations<ArrowRight size={13} aria-hidden="true" /></Link>
      </div>

      <dl className="overviewFacts compactFacts">
        <div><dt>Recent conversations</dt><dd>{data.conversations.length}</dd></div>
        <div><dt>Open knowledge gaps</dt><dd>{data.reviewTotal}</dd></div>
      </dl>
      <p className="reviewFilterNote">Recent conversations reflect a bounded window of up to {recentWindowLimit} per assistant, not an all-time total.</p>

      {data.reviewItems.length > 0 ? (
        <>
          <div className="qualityBreakdown">
            <h4>Open review items by answer state</h4>
            <dl className="overviewFacts compactFacts">
              <div><dt>Fallback</dt><dd>{stateCounts.fallback}</dd></div>
              <div><dt>Low confidence</dt><dd>{stateCounts.low_confidence}</dd></div>
              <div><dt>Failed</dt><dd>{stateCounts.failed}</dd></div>
              <div><dt>With citations</dt><dd>{withCitations}/{data.reviewItems.length}</dd></div>
            </dl>
          </div>
          <p className="reviewFilterNote">Latency and citation figures are computed only from the {data.reviewItems.length} open review item{data.reviewItems.length === 1 ? "" : "s"} sampled above, not all conversations. Average sampled latency: {averageLatency === null ? "no sample" : `${averageLatency} ms`}.</p>
        </>
      ) : (
        <p className="reviewFilterNote">No open review items in the current sample, so no fallback/low-confidence/failed breakdown is available.</p>
      )}
    </section>
  );
}
