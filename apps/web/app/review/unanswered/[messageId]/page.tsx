import { AccessDeniedState, ErrorState } from "../../../../components/conversations/state-panels";
import { NoAssistantSelectedState, ReviewItemNotFoundState } from "../../../../components/review/review-empty-states";
import { ReviewDetailView } from "../../../../components/review/review-detail-view";
import { getUnansweredReviewItem } from "../../../../lib/api/review";
import { DashboardApiError, isDashboardApiError, messageForApiError } from "../../../../lib/api/errors";
import { getWidgetDetail } from "../../../../lib/api/widgets";
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
  if (!query.assistant) return <NoAssistantSelectedState />;

  const [result, assistantResult] = await Promise.all([
    loadReviewDetail(session, messageId, query.assistant),
    loadAssistant(session, query.assistant),
  ]);

  if (!result.ok) {
    if (result.error.kind === "forbidden") return <AccessDeniedState />;
    if (result.error.kind === "not_found") return <ReviewItemNotFoundState assistantId={query.assistant} />;
    return <ErrorState message={messageForApiError(result.error)} retryHref={`/review/unanswered/${messageId}?assistant=${query.assistant}`} />;
  }
  if (!assistantResult.ok) {
    if (assistantResult.error.kind === "forbidden") return <AccessDeniedState />;
    return <ErrorState message={messageForApiError(assistantResult.error)} retryHref={`/review/unanswered/${messageId}?assistant=${query.assistant}`} />;
  }

  const canUpdate = session.role === "org_owner" || session.role === "client_admin" || session.role === "super_admin";
  return <ReviewDetailView detail={result.data} assistant={assistantResult.data} session={session} canUpdate={canUpdate} />;
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

async function loadAssistant(session: DevelopmentDashboardSession, assistantId: string) {
  try {
    const response = await getWidgetDetail(session, assistantId);
    return { ok: true as const, data: response.data };
  } catch (error) {
    if (isDashboardApiError(error)) return { ok: false as const, error };
    return { ok: false as const, error: new DashboardApiError("unknown", "Unexpected dashboard error.") };
  }
}
