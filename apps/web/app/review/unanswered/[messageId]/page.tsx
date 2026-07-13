import { AccessDeniedState, ErrorState, MissingTenantConfiguration } from "../../../../components/conversations/state-panels";
import { ReviewDetail } from "../../../../components/review/review-detail";
import { getUnansweredReviewItem } from "../../../../lib/api/review";
import { DashboardApiError, isDashboardApiError, messageForApiError } from "../../../../lib/api/errors";
import type { ReviewItemDetail } from "../../../../lib/api/types";
import { getDevelopmentDashboardSession, type DevelopmentDashboardSession } from "../../../../lib/auth/development-session";

export const dynamic = "force-dynamic";

type ReviewDetailPageProps = {
  params: Promise<{ messageId: string }>;
};

export default async function ReviewDetailPage({ params }: ReviewDetailPageProps) {
  const { messageId } = await params;
  const tenant = getDevelopmentDashboardSession();

  if (!tenant.configured) {
    return <MissingTenantConfiguration missing={tenant.missing} invalid={tenant.invalid} />;
  }

  const result = await loadReviewDetail(tenant.session, messageId);
  if (!result.ok) {
    if (result.error.kind === "forbidden") return <AccessDeniedState />;
    return <ErrorState message={messageForApiError(result.error)} retryHref={`/review/unanswered/${messageId}`} />;
  }

  const canUpdate = tenant.session.role === "org_owner" || tenant.session.role === "client_admin" || tenant.session.role === "super_admin";
  return <ReviewDetail detail={result.data} session={tenant.session} canUpdate={canUpdate} />;
}

async function loadReviewDetail(
  session: DevelopmentDashboardSession,
  messageId: string,
): Promise<{ ok: true; data: ReviewItemDetail } | { ok: false; error: DashboardApiError }> {
  try {
    const response = await getUnansweredReviewItem(session, messageId);
    return { ok: true, data: response.data };
  } catch (error) {
    if (isDashboardApiError(error)) return { ok: false, error };
    return { ok: false, error: new DashboardApiError("unknown", "Unexpected dashboard error.") };
  }
}
