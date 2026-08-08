import { NoAssistantSelectedState } from "../../../../components/conversations/conversation-empty-states";
import { CandidateCreateForm } from "../../../../components/feedback-loop/candidate-create-form";
import { requireDashboardSession } from "../../../../lib/auth/session";

export const dynamic = "force-dynamic";

type CandidateCreatePageProps = {
  searchParams: Promise<{ assistant?: string; source_type?: string; source_id?: string; prefill_question?: string; prefill_response?: string }>;
};

export default async function CandidateCreatePage({ searchParams }: CandidateCreatePageProps) {
  const params = await searchParams;
  const session = await requireDashboardSession();
  if (!params.assistant) return <NoAssistantSelectedState />;

  return (
    <section className="observabilityPage">
      <CandidateCreateForm
        session={session}
        assistantId={params.assistant}
        sourceType={params.source_type}
        sourceId={params.source_id}
        prefillQuestion={params.prefill_question}
        prefillResponse={params.prefill_response}
      />
    </section>
  );
}
