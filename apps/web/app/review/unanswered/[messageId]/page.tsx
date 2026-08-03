import { AccessDeniedState, ErrorState } from "../../../../components/conversations/state-panels";
import { ReviewDetail } from "../../../../components/review/review-detail";
import { getUnansweredReviewItem } from "../../../../lib/api/review";
import { DashboardApiError, isDashboardApiError, messageForApiError } from "../../../../lib/api/errors";
import type { ReviewItemDetail } from "../../../../lib/api/types";
import type { DevelopmentDashboardSession } from "../../../../lib/auth/development-session";
import { requireDashboardSession } from "../../../../lib/auth/session";

export const dynamic = "force-dynamic";

type ReviewDetailPageProps = {
  params: Promise<{ messageId: string }>;
  searchParams: Promise<{ assistant?: string }>;
};

export default async function ReviewDetailPage({ params, searchParams }: ReviewDetailPageProps) {
  const { messageId } = await params;
  const query = await searchParams;
  const session = await requireDashboardSession();
  if (!query.assistant) return <ErrorState message="Assistant context is required for review detail." retryHref="/review/unanswered" />;

  const result = await loadReviewDetail(session, messageId, query.assistant);
  if (!result.ok) {
    if (result.error.kind === "forbidden") return <AccessDeniedState />;
    return <ErrorState message={messageForApiError(result.error)} retryHref={`/review/unanswered/${messageId}?assistant=${query.assistant}`} />;
  }

  const canUpdate = session.role === "org_owner" || session.role === "client_admin" || session.role === "super_admin";
  return <ReviewDetail detail={result.data} session={session} canUpdate={canUpdate} />;
}

async function loadReviewDetail(
  session: DevelopmentDashboardSession,
  messageId: string,
  assistantId: string,
): Promise<{ ok: true; data: ReviewItemDetail } | { ok: false; error: DashboardApiError }> {
  try {
    const response = await getUnansweredReviewItem(session, messageId, assistantId);
    return { ok: true, data: response.data };
  } catch (error) {
    if (isDashboardApiError(error)) return { ok: false, error };
    return { ok: false, error: new DashboardApiError("unknown", "Unexpected dashboard error.") };
  }
}
