"use client";

import { motion, useReducedMotion } from "framer-motion";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useRef, useState, type FormEvent, type ReactNode } from "react";
import {
  ArrowRight,
  BarChart3,
  Bot,
  Check,
  ChevronLeft,
  Clipboard,
  FileText,
  Globe2,
  Loader2,
  LockKeyhole,
  MessageSquareText,
  Rocket,
  ShieldCheck,
  Sparkles,
  UploadCloud,
} from "lucide-react";

import { completeOnboarding } from "../../lib/api/auth";
import { answerChatbotQuestion } from "../../lib/api/chatbot";
import { isDashboardApiError } from "../../lib/api/errors";
import {
  activateWidgetPublicCredential,
  addWidgetOrigin,
  createWidget,
  getWidgetEmbed,
  publishWidget,
  updateWidgetKnowledgeScope,
  validateWidgetPublish,
  type WidgetDetail,
  type WidgetEmbedMetadata,
  type WidgetRevisionDetail,
} from "../../lib/api/widgets";
import { chunkDocumentVersion, embedDocumentVersion, extractDocumentVersion, transitionDocument, uploadDocument, type DocumentUploadResult } from "../../lib/api/documents";
import type { RAGAnswerResponse } from "../../lib/api/types";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";

type WizardStep = "welcome" | "details" | "company" | "knowledge" | "training" | "playground" | "publish";
type ProgressStatus = "waiting" | "active" | "complete" | "error";

type AssistantForm = {
  assistantName: string;
  description: string;
  purpose: string;
  language: string;
  companyName: string;
  websiteUrl: string;
  industry: string;
  knowledgeUrl: string;
};

type TrainingStepState = { key: string; label: string; detail: string; status: ProgressStatus };

type PlaygroundMessage = {
  id: string;
  question: string;
  answer: RAGAnswerResponse;
};

const steps: Array<{ id: WizardStep; label: string; icon: typeof Sparkles }> = [
  { id: "welcome", label: "Welcome", icon: Sparkles },
  { id: "details", label: "Assistant", icon: Bot },
  { id: "company", label: "Company", icon: Globe2 },
  { id: "knowledge", label: "Knowledge", icon: UploadCloud },
  { id: "training", label: "Training", icon: BarChart3 },
  { id: "playground", label: "Playground", icon: MessageSquareText },
  { id: "publish", label: "Publish", icon: Rocket },
];

const initialForm: AssistantForm = {
  assistantName: "Customer Support Assistant",
  description: "Answers customer questions from approved business knowledge.",
  purpose: "customer_support",
  language: "en",
  companyName: "",
  websiteUrl: "",
  industry: "software",
  knowledgeUrl: "",
};

const trainingTemplate: TrainingStepState[] = [
  { key: "upload", label: "Upload", detail: "Securely store selected files", status: "waiting" },
  { key: "extract", label: "Extract", detail: "Read PDF, DOCX, and text content", status: "waiting" },
  { key: "chunk", label: "Chunk", detail: "Split knowledge into retrieval-ready passages", status: "waiting" },
  { key: "embed", label: "Embed", detail: "Create searchable semantic vectors", status: "waiting" },
  { key: "index", label: "Index", detail: "Attach ready sources to the assistant draft", status: "waiting" },
  { key: "completion", label: "Completion", detail: "Assistant is ready for testing", status: "waiting" },
];

export function AssistantOnboardingWizard({ session }: { session: DevelopmentDashboardSession }) {
  const router = useRouter();
  const reduceMotion = useReducedMotion();
  const [step, setStep] = useState<WizardStep>("welcome");
  const [form, setForm] = useState<AssistantForm>({ ...initialForm, companyName: session.organisationName || "" });
  const [files, setFiles] = useState<File[]>([]);
  const [widget, setWidget] = useState<WidgetDetail | null>(null);
  const [draft, setDraft] = useState<WidgetRevisionDetail | null>(null);
  const [documentIds, setDocumentIds] = useState<string[]>([]);
  const [training, setTraining] = useState(trainingTemplate);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [question, setQuestion] = useState("What can this assistant help customers with?");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<PlaygroundMessage[]>([]);
  const [embed, setEmbed] = useState<WidgetEmbedMetadata | null>(null);
  const [publishErrors, setPublishErrors] = useState<string[]>([]);
  const sequence = useRef(0);

  const activeIndex = steps.findIndex((item) => item.id === step);
  const canContinue = useMemo(() => validateStep(step, form, files) === null && !busy, [step, form, files, busy]);
  const completion = Math.round(((activeIndex + 1) / steps.length) * 100);

  function updateForm<K extends keyof AssistantForm>(key: K, value: AssistantForm[K]) {
    setForm((current) => ({ ...current, [key]: value }));
    setError(null);
    if (key === "websiteUrl") {
      const inferred = inferCompanyName(value);
      if (inferred && !form.companyName.trim()) setForm((current) => ({ ...current, websiteUrl: value, companyName: inferred }));
    }
  }

  async function next() {
    const validation = validateStep(step, form, files);
    if (validation) {
      setError(validation);
      return;
    }
    setError(null);
    if (step === "details") await ensureAssistant();
    setStep(steps[Math.min(activeIndex + 1, steps.length - 1)].id);
  }

  function back() {
    if (busy) return;
    setError(null);
    setStep(steps[Math.max(activeIndex - 1, 0)].id);
  }

  async function ensureAssistant() {
    if (widget) return widget;
    setBusy(true);
    setNotice("Creating assistant draft...");
    try {
      const response = await createWidget(session, {
        display_name: form.assistantName.trim(),
        environment: "production",
        initial_configuration: {
          bot_name: form.assistantName.trim(),
          welcome_message: form.description.trim() || `Ask ${form.companyName || "our team"} a question.`,
          launcher_label: "Ask AI",
          primary_colour: "#1B2A4A",
          secondary_colour: "#F7F5F0",
          language: form.language,
          show_citations: true,
          allow_conversation_history: true,
          suggested_questions_json: suggestedQuestions(form.purpose),
          max_initial_suggestions: 3,
          privacy_notice_url: normaliseUrl(form.websiteUrl) || null,
        },
      });
      setWidget(response.data);
      setDraft(response.data.draft ?? null);
      return response.data;
    } catch (caught) {
      const message = messageForError(caught, "Assistant could not be created.");
      setError(message);
      throw caught;
    } finally {
      setBusy(false);
      setNotice(null);
    }
  }

  async function trainAssistant() {
    setBusy(true);
    setError(null);
    setNotice(null);
    setTraining(trainingTemplate.map((item) => ({ ...item, status: item.key === "upload" ? "active" : "waiting" })));
    try {
      const currentWidget = await ensureAssistant();
      const uploaded: DocumentUploadResult[] = [];
      for (const file of files) {
        const result = await uploadDocument(session, { file, title: file.name, category: "onboarding", visibility: "workspace", assistantId: currentWidget.id });
        uploaded.push(result.data);
      }
      setStepStatus("upload", "complete");

      const readyIds: string[] = [];
      for (const item of uploaded) {
        setStepStatus("extract", "active");
        await extractDocumentVersion(session, item.document.id, item.document_version.id);
        setStepStatus("extract", "complete");
        setStepStatus("chunk", "active");
        await chunkDocumentVersion(session, item.document.id, item.document_version.id);
        setStepStatus("chunk", "complete");
        setStepStatus("embed", "active");
        await embedDocumentVersion(session, item.document.id, item.document_version.id);
        setStepStatus("embed", "complete");
        await transitionDocument(session, item.document.id, "ready");
        readyIds.push(item.document.id);
      }

      setStepStatus("index", "active");
      const activeDraft = draft ?? currentWidget.draft;
      if (!activeDraft) throw new Error("Assistant draft is unavailable.");
      const scoped = await updateWidgetKnowledgeScope(session, currentWidget.id, {
        document_ids: readyIds,
        expected_concurrency_version: activeDraft.concurrency_version,
      });
      setDraft(scoped.data);
      setDocumentIds(readyIds);
      setStepStatus("index", "complete");
      setStepStatus("completion", "complete");
      setNotice("Training complete. Your assistant is ready to test.");
    } catch (caught) {
      setTraining((current) => current.map((item) => item.status === "active" ? { ...item, status: "error" } : item));
      setError(messageForError(caught, "Training could not be completed."));
    } finally {
      setBusy(false);
    }
  }

  async function askQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const query = question.trim();
    if (!query || busy) return;
    setBusy(true);
    setError(null);
    try {
      const currentWidget = await ensureAssistant();
      const response = await answerChatbotQuestion(session, { query, conversationId, assistantId: currentWidget.id });
      setConversationId(response.data.conversation_id);
      setMessages((current) => [...current, { id: `playground-${++sequence.current}`, question: query, answer: response.data }]);
      setQuestion("");
    } catch (caught) {
      setError(messageForError(caught, "The playground request could not be completed."));
    } finally {
      setBusy(false);
    }
  }

  async function publishAssistant() {
    const currentWidget = widget;
    const currentDraft = draft ?? widget?.draft;
    if (!currentWidget || !currentDraft) {
      setError("Create and train the assistant before publishing.");
      return;
    }
    setBusy(true);
    setError(null);
    setPublishErrors([]);
    try {
      const origin = normaliseOrigin(form.websiteUrl);
      if (origin) await addWidgetOrigin(session, currentWidget.id, origin);
      await activateWidgetPublicCredential(session, currentWidget.public_credential_id);
      const validation = await validateWidgetPublish(session, currentWidget.id, {
        draft_revision_id: currentDraft.id,
        expected_concurrency_version: currentDraft.concurrency_version,
      });
      if (!validation.data.publishable) {
        setPublishErrors(validation.data.errors.map((item) => item.message));
        return;
      }
      await publishWidget(session, currentWidget.id, {
        draft_revision_id: currentDraft.id,
        expected_concurrency_version: currentDraft.concurrency_version,
      });
      const embedResponse = await getWidgetEmbed(session, currentWidget.id);
      setEmbed(embedResponse.data);
      setNotice("Assistant published. Your embed code is ready.");
    } catch (caught) {
      setError(messageForError(caught, "Assistant could not be published."));
    } finally {
      setBusy(false);
    }
  }

  async function finish() {
    setBusy(true);
    setError(null);
    try {
      await completeOnboarding();
      router.push("/dashboard");
      router.refresh();
    } catch (caught) {
      setError(messageForError(caught, "Onboarding could not be completed."));
    } finally {
      setBusy(false);
    }
  }

  function setStepStatus(key: string, status: ProgressStatus) {
    setTraining((current) => current.map((item) => item.key === key ? { ...item, status } : item));
  }

  return (
    <main className="assistantWizardPage">
      <aside className="assistantWizardRail" aria-label="Onboarding progress">
        <Link className="wizardBrand" href="/">
          <Image src="/brand/conversa-icon.svg" alt="" aria-hidden="true" width={42} height={42} />
          <span>Conversa</span>
        </Link>
        <div className="wizardProgressMeter" aria-label={`Onboarding ${completion}% complete`}>
          <span style={{ width: `${completion}%` }} />
        </div>
        <ol className="wizardSteps">
          {steps.map((item, index) => {
            const Icon = item.icon;
            const state = index < activeIndex ? "complete" : index === activeIndex ? "active" : "waiting";
            return <li key={item.id} data-state={state}><Icon size={17} /><span>{item.label}</span></li>;
          })}
        </ol>
        <div className="wizardRailCard">
          <ShieldCheck size={18} />
          <strong>Tenant-secure setup</strong>
          <p>Your assistant, sources, preview, and widget publish state stay inside the authenticated workspace.</p>
        </div>
      </aside>

      <section className="assistantWizardShell">
        <motion.div key={step} initial={{ opacity: 0, y: reduceMotion ? 0 : 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.28 }} className="wizardPanel">
          {notice ? <p className="wizardNotice" role="status">{notice}</p> : null}
          {error ? <p className="wizardError" role="alert">{error}</p> : null}
          {step === "welcome" ? <WelcomeStep /> : null}
          {step === "details" ? <DetailsStep form={form} updateForm={updateForm} /> : null}
          {step === "company" ? <CompanyStep form={form} updateForm={updateForm} /> : null}
          {step === "knowledge" ? <KnowledgeStep form={form} files={files} setFiles={setFiles} updateForm={updateForm} /> : null}
          {step === "training" ? <TrainingStep training={training} files={files} documentIds={documentIds} busy={busy} onTrain={trainAssistant} /> : null}
          {step === "playground" ? <PlaygroundStep question={question} setQuestion={setQuestion} messages={messages} busy={busy} onSubmit={askQuestion} /> : null}
          {step === "publish" ? <PublishStep form={form} widget={widget} embed={embed} errors={publishErrors} busy={busy} onPublish={publishAssistant} onFinish={finish} /> : null}
        </motion.div>

        <div className="wizardActions">
          <button type="button" className="wizardSecondary" onClick={back} disabled={activeIndex === 0 || busy}><ChevronLeft size={17} /> Back</button>
          {step !== "publish" ? <button type="button" className="wizardPrimary" onClick={next} disabled={!canContinue}>{busy ? <Loader2 size={17} className="spin" /> : null}{step === "welcome" ? "Create Your First AI Assistant" : "Continue"}<ArrowRight size={17} /></button> : null}
        </div>
      </section>
    </main>
  );
}

function WelcomeStep() {
  return <div className="wizardHeroStep"><span className="wizardKicker">Create AI Assistant</span><h1>Create Your First AI Assistant</h1><p>An assistant is a branded, source-grounded chatbot that answers from your approved knowledge, can be tested by your team, and can be published as a secure website widget.</p><div className="wizardValueGrid"><Value icon={<FileText size={18} />} title="Grounded" text="Uses the files and sources you approve." /><Value icon={<MessageSquareText size={18} />} title="Testable" text="Validate answers with citations before launch." /><Value icon={<Rocket size={18} />} title="Deployable" text="Publish a widget and embed it on your website." /></div></div>;
}

function DetailsStep({ form, updateForm }: { form: AssistantForm; updateForm: <K extends keyof AssistantForm>(key: K, value: AssistantForm[K]) => void }) {
  return <div className="wizardFormStep"><StepHeader kicker="Assistant Details" title="Define how the assistant should appear and respond" text="This creates the first draft. You can refine it later from widget administration." /><div className="wizardFieldGrid"><WizardField label="Assistant name"><input value={form.assistantName} onChange={(event) => updateForm("assistantName", event.currentTarget.value)} maxLength={120} required /></WizardField><WizardField label="Purpose"><select value={form.purpose} onChange={(event) => updateForm("purpose", event.currentTarget.value)}><option value="customer_support">Customer support</option><option value="sales_enablement">Sales enablement</option><option value="employee_knowledge">Employee knowledge</option><option value="education">Education and admissions</option></select></WizardField><WizardField label="Default language"><select value={form.language} onChange={(event) => updateForm("language", event.currentTarget.value)}><option value="en">English</option><option value="en-AU">English (Australia)</option><option value="en-US">English (United States)</option><option value="fr">French</option><option value="de">German</option><option value="es">Spanish</option></select></WizardField><WizardField label="Assistant description" wide><textarea value={form.description} onChange={(event) => updateForm("description", event.currentTarget.value)} rows={4} maxLength={280} /></WizardField></div></div>;
}

function CompanyStep({ form, updateForm }: { form: AssistantForm; updateForm: <K extends keyof AssistantForm>(key: K, value: AssistantForm[K]) => void }) {
  return <div className="wizardFormStep"><StepHeader kicker="Company" title="Connect the assistant to your brand context" text="Conversa will infer simple branding from your company details where possible. The official palette remains available for refinement later." /><div className="wizardFieldGrid"><WizardField label="Company name"><input value={form.companyName} onChange={(event) => updateForm("companyName", event.currentTarget.value)} autoComplete="organization" /></WizardField><WizardField label="Website URL"><input value={form.websiteUrl} onChange={(event) => updateForm("websiteUrl", event.currentTarget.value)} placeholder="https://example.com" inputMode="url" /></WizardField><WizardField label="Industry"><select value={form.industry} onChange={(event) => updateForm("industry", event.currentTarget.value)}><option value="software">Software and SaaS</option><option value="financial_services">Financial services</option><option value="healthcare">Healthcare</option><option value="education">Education</option><option value="professional_services">Professional services</option><option value="retail">Retail and commerce</option></select></WizardField><div className="brandAutofill"><span style={{ background: "#1B2A4A" }} /><div><strong>{form.companyName || "Company brand"}</strong><p>{normaliseOrigin(form.websiteUrl) || "Add a website URL to prepare publishing origin."}</p></div></div></div></div>;
}

function KnowledgeStep({ form, files, setFiles, updateForm }: { form: AssistantForm; files: File[]; setFiles: (files: File[]) => void; updateForm: <K extends keyof AssistantForm>(key: K, value: AssistantForm[K]) => void }) {
  return <div className="wizardFormStep"><StepHeader kicker="Knowledge Sources" title="Upload the first trusted sources" text="PDF, DOCX, and TXT files are processed through the authenticated workspace knowledge pipeline." /><label className="uploadDropzone"><UploadCloud size={24} /><strong>Upload PDF, DOCX, or TXT</strong><span>{files.length ? `${files.length} file${files.length === 1 ? "" : "s"} selected` : "Choose source files to train the assistant"}</span><input aria-label="Upload knowledge files" type="file" multiple accept=".pdf,.docx,.txt,application/pdf,text/plain,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={(event) => setFiles(Array.from(event.currentTarget.files ?? []))} /></label>{files.length ? <ul className="fileList">{files.map((file) => <li key={`${file.name}-${file.size}`}><FileText size={16} />{file.name}<span>{formatBytes(file.size)}</span></li>)}</ul> : null}<div className="wizardFieldGrid"><WizardField label="Website URL"><input value={form.knowledgeUrl} onChange={(event) => updateForm("knowledgeUrl", event.currentTarget.value)} placeholder="Website crawler coming soon" disabled /></WizardField></div><div className="comingSoonGrid"><ComingSoon title="Notion" /><ComingSoon title="Google Drive" /><ComingSoon title="SharePoint" /></div></div>;
}

function TrainingStep({ training, files, documentIds, busy, onTrain }: { training: TrainingStepState[]; files: File[]; documentIds: string[]; busy: boolean; onTrain: () => void }) {
  const complete = training.every((item) => item.status === "complete");
  return <div className="wizardFormStep"><StepHeader kicker="Training" title="Process and index your knowledge" text="Each stage reports state as the backend accepts, extracts, chunks, embeds, and scopes your sources." /><div className="trainingTimeline">{training.map((item) => <div key={item.key} className="trainingItem" data-status={item.status}><span>{item.status === "active" ? <Loader2 size={17} className="spin" /> : item.status === "complete" ? <Check size={17} /> : item.status === "error" ? "!" : null}</span><div><strong>{item.label}</strong><p>{item.detail}</p></div></div>)}</div><div className="trainingSummary"><strong>{files.length} files queued</strong><span>{documentIds.length} indexed sources</span></div><button type="button" className="wizardPrimary" onClick={onTrain} disabled={busy || files.length === 0 || complete}>{busy ? "Training" : complete ? "Training complete" : "Start training"}</button></div>;
}

function PlaygroundStep({ question, setQuestion, messages, busy, onSubmit }: { question: string; setQuestion: (value: string) => void; messages: PlaygroundMessage[]; busy: boolean; onSubmit: (event: FormEvent<HTMLFormElement>) => void }) {
  return <div className="wizardFormStep"><StepHeader kicker="Playground" title="Test the assistant with authenticated chat" text="Review answer quality, citations, confidence, source references, and latency before publishing." /><div className="playgroundFrame">{messages.length === 0 ? <div className="playgroundEmpty"><Bot size={22} /><strong>No test messages yet</strong><p>Ask a realistic customer question to evaluate the assistant.</p></div> : messages.map((message) => <article className="playgroundAnswer" key={message.id}><p className="playgroundQuestion">{message.question}</p><p>{message.answer.answer}</p><div className="answerMetrics"><span>{confidenceLabel(message.answer.answer_state)}</span><span>{message.answer.latency_ms} ms</span><span>{message.answer.retrieved_chunk_count} sources</span></div>{message.answer.citations.length ? <div className="sourceRefs">{message.answer.citations.map((citation) => <span key={`${citation.chunk_id}-${citation.citation_index}`}>[{citation.citation_index}] {citation.source_title}</span>)}</div> : <p className="mutedInline">No citations returned for this answer.</p>}</article>)}</div><form className="playgroundComposer" onSubmit={onSubmit}><textarea aria-label="Playground question" value={question} onChange={(event) => setQuestion(event.currentTarget.value)} rows={3} maxLength={4000} /><button className="wizardPrimary" disabled={busy || question.trim().length === 0}>{busy ? "Testing" : "Ask assistant"}</button></form></div>;
}

function PublishStep({ form, widget, embed, errors, busy, onPublish, onFinish }: { form: AssistantForm; widget: WidgetDetail | null; embed: WidgetEmbedMetadata | null; errors: string[]; busy: boolean; onPublish: () => void; onFinish: () => void }) {
  const snippet = embed?.snippet || widget ? `<script async src="https://cdn.example.com/widget-sdk/v1/loader.js" data-widget-key="${widget?.public_identifier || "pending"}"></script>` : "";
  return <div className="wizardFormStep"><StepHeader kicker="Publish" title="Launch the assistant widget" text="Publish only when validation passes. The embed snippet stays inert here and can be copied after publishing." /><div className="publishGrid"><div className="widgetPreview"><div><span style={{ background: "#1B2A4A" }} /><strong>{form.assistantName}</strong></div><p>{form.description}</p><button type="button">Ask AI</button></div><div className="embedCard"><div><strong>Embed code</strong><button type="button" className="copyButton" disabled={!snippet} onClick={() => navigator.clipboard?.writeText(snippet)}><Clipboard size={15} /> Copy</button></div><pre>{snippet || "Create the assistant to generate embed code."}</pre></div></div>{errors.length ? <ul className="publishErrors" role="alert">{errors.map((item) => <li key={item}>{item}</li>)}</ul> : null}{embed?.published ? <div className="successPanel"><Check size={18} /><div><strong>Published successfully</strong><p>The widget is ready for {normaliseOrigin(form.websiteUrl) || "your approved website"}.</p></div></div> : null}<div className="publishActions"><button type="button" className="wizardPrimary" disabled={busy || !widget} onClick={onPublish}>{busy ? "Publishing" : "Publish assistant"}</button><button type="button" className="wizardSecondary" disabled={busy || !embed?.published} onClick={onFinish}>Finish onboarding</button></div></div>;
}

function StepHeader({ kicker, title, text }: { kicker: string; title: string; text: string }) {
  return <header className="wizardStepHeader"><span className="wizardKicker">{kicker}</span><h1>{title}</h1><p>{text}</p></header>;
}

function WizardField({ label, children, wide = false }: { label: string; children: ReactNode; wide?: boolean }) {
  return <label className="wizardField" data-wide={wide}><span>{label}</span>{children}</label>;
}

function Value({ icon, title, text }: { icon: React.ReactNode; title: string; text: string }) {
  return <article><span>{icon}</span><strong>{title}</strong><p>{text}</p></article>;
}

function ComingSoon({ title }: { title: string }) {
  return <div className="comingSoon"><LockKeyhole size={16} /><strong>{title}</strong><span>Coming Soon</span></div>;
}

function validateStep(step: WizardStep, form: AssistantForm, files: File[]) {
  if (step === "details") {
    if (form.assistantName.trim().length < 2) return "Enter an assistant name.";
    if (form.description.trim().length < 12) return "Add a short assistant description.";
  }
  if (step === "company") {
    if (form.companyName.trim().length < 2) return "Enter your company name.";
    if (form.websiteUrl.trim() && !normaliseUrl(form.websiteUrl)) return "Enter a valid website URL.";
  }
  if (step === "knowledge" && files.length === 0) return "Upload at least one PDF, DOCX, or TXT source.";
  return null;
}

function suggestedQuestions(purpose: string) {
  if (purpose === "sales_enablement") return ["Which plan should I choose?", "What makes this different?", "Can I book a demo?"];
  if (purpose === "employee_knowledge") return ["Where can I find policy details?", "How does this process work?", "Who owns this topic?"];
  if (purpose === "education") return ["How do I apply?", "What documents are required?", "When are key dates?"];
  return ["How can you help?", "Where can I find pricing?", "How do I contact support?"];
}

function normaliseUrl(value: string) {
  const trimmed = value.trim();
  if (!trimmed) return "";
  try {
    const url = new URL(trimmed.startsWith("http") ? trimmed : `https://${trimmed}`);
    if (!/^https?:$/.test(url.protocol)) return "";
    return url.toString();
  } catch {
    return "";
  }
}

function normaliseOrigin(value: string) {
  const normalized = normaliseUrl(value);
  if (!normalized) return "";
  const url = new URL(normalized);
  return url.origin;
}

function inferCompanyName(value: string) {
  try {
    const host = new URL(value.startsWith("http") ? value : `https://${value}`).hostname.replace(/^www\./, "");
    const label = host.split(".")[0];
    return label ? label.charAt(0).toUpperCase() + label.slice(1) : "";
  } catch {
    return "";
  }
}

function formatBytes(size: number) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${Math.round(size / 1024)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function confidenceLabel(state: string) {
  if (state === "answered") return "High confidence";
  if (state === "low_confidence") return "Needs review";
  if (state === "fallback") return "Fallback used";
  return "Pending review";
}

function messageForError(error: unknown, fallback: string) {
  if (isDashboardApiError(error)) {
    if (error.kind === "validation") return "Check the highlighted setup details and try again.";
    if (error.kind === "forbidden") return "Your account does not have permission to complete this setup.";
    if (error.kind === "network") return "The API could not be reached. Check that the backend is running.";
    if (error.kind === "conflict") return "The assistant draft changed. Refresh and try again.";
  }
  return fallback;
}
