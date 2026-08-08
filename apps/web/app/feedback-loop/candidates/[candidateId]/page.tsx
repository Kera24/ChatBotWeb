import { AccessDeniedState, ErrorState } from "../../../../components/conversations/state-panels";
import { CandidateDetailView } from "../../../../components/feedback-loop/candidate-detail-view";
import { DashboardApiError, isDashboardApiError, messageForApiError } from "../../../../lib/api/errors";
import { getEvaluationCandidate } from "../../../../lib/api/feedback-loop";
import { requireDashboardSession } from "../../../../lib/auth/session";

export const dynamic = "force-dynamic";

type CandidateDetailPageProps = {
  params: Promise<{ candidateId: string }>;
};

export default async function CandidateDetailPage({ params }: CandidateDetailPageProps) {
  const { candidateId } = await params;
  const session = await requireDashboardSession();

  let detailResult;
  try {
    const response = await getEvaluationCandidate(session, candidateId);
    detailResult = { ok: true as const, data: response.data };
  } catch (error) {
    detailResult = { ok: false as const, error: isDashboardApiError(error) ? error : new DashboardApiError("unknown", "Unexpected dashboard error.") };
  }

  if (!detailResult.ok) {
    if (detailResult.error.kind === "forbidden") return <AccessDeniedState />;
    if (detailResult.error.kind === "not_found") {
      return (
        <section className="statePanel" role="status">
          <h2>Candidate not found</h2>
          <p>This production candidate does not exist in the current workspace.</p>
        </section>
      );
    }
    return <ErrorState message={messageForApiError(detailResult.error)} retryHref={`/feedback-loop/candidates/${candidateId}`} />;
  }

  const canTriage = session.role === "org_owner" || session.role === "client_admin" || session.role === "super_admin";

  return (
    <CandidateDetailView
      session={session}
      candidate={detailResult.data.candidate}
      potentialDuplicates={detailResult.data.potential_duplicates}
      sourceTracePublicId={detailResult.data.source_trace_public_id}
      canTriage={canTriage}
    />
  );
}
