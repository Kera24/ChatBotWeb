"use client";

import { useState } from "react";

import { updateUnansweredReviewStatus } from "../../lib/api/review";
import type { ReviewItem } from "../../lib/api/types";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";
import { isDashboardApiError, messageForApiError } from "../../lib/api/errors";
import { ReviewStatusBadge } from "./review-status-badge";

type ReviewDecisionFormProps = {
  session: DevelopmentDashboardSession;
  item: ReviewItem;
  canUpdate: boolean;
};

const statuses = [
  { value: "reviewed", label: "Mark reviewed" },
  { value: "dismissed", label: "Dismiss" },
  { value: "knowledge_gap", label: "Mark knowledge gap" },
  { value: "open", label: "Reopen" },
];

export function ReviewDecisionForm({ session, item, canUpdate }: ReviewDecisionFormProps) {
  const [current, setCurrent] = useState(item);
  const [note, setNote] = useState(item.reviewer_note ?? "");
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submitStatus(status: string) {
    setPending(status);
    setError(null);
    try {
      const response = await updateUnansweredReviewStatus(session, item.assistant_message_id, {
        review_status: status,
        reviewer_note: note || null,
      });
      setCurrent(response.data);
    } catch (caught) {
      if (isDashboardApiError(caught)) {
        setError(messageForApiError(caught));
      } else {
        setError("The review decision could not be saved.");
      }
    } finally {
      setPending(null);
    }
  }

  return (
    <section className="reviewDecisionPanel" aria-labelledby="review-decision-title">
      <div>
        <p className="sectionKicker">Reviewer decision</p>
        <h2 id="review-decision-title">What should happen next?</h2>
      </div>
      <ReviewStatusBadge status={current.review_status} />
      {current.reviewed_at ? <p>Last reviewed {new Date(current.reviewed_at).toLocaleString()}</p> : null}
      <label>
        <span>Reviewer note</span>
        <textarea
          value={note}
          onChange={(event) => setNote(event.target.value)}
          disabled={!canUpdate}
          rows={4}
          aria-label="Reviewer note"
        />
      </label>
      {!canUpdate ? <p className="mutedText">Viewers can inspect review items but cannot change review status.</p> : null}
      <div className="reviewDecisionActions" aria-label="Review status actions">
        {statuses.map((status) => (
          <button
            className="actionButton"
            type="button"
            key={status.value}
            disabled={!canUpdate || pending !== null}
            onClick={() => submitStatus(status.value)}
          >
            {pending === status.value ? "Saving" : status.label}
          </button>
        ))}
      </div>
      {error ? <p className="errorText" role="alert">{error}</p> : null}
    </section>
  );
}
