"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import Image from "next/image";
import Link from "next/link";
import { useMemo, useState, type ReactNode } from "react";
import {
  ArrowRight,
  BarChart3,
  Bot,
  Building2,
  Check,
  ChevronDown,
  Database,
  FileText,
  LockKeyhole,
  MessageSquareText,
  MousePointerClick,
  Network,
  ShieldCheck,
  Sparkles,
  UploadCloud,
  UsersRound,
} from "lucide-react";

const trustedLogos = ["Aster", "Northline", "Meridian", "Cobalt", "Atlas", "Halcyon"];

const features = [
  { title: "Knowledge Base", description: "Upload policies, handbooks, FAQs, and internal documentation into one governed source layer.", icon: Database },
  { title: "AI Chatbot", description: "Test source-grounded answers before customers see them, with citations and reviewable conversation history.", icon: Bot },
  { title: "Widgets", description: "Deploy polished assistant widgets across approved customer touchpoints with controlled presentation settings.", icon: MousePointerClick },
  { title: "Analytics", description: "Monitor usage, answer quality signals, failed sources, open gaps, and deployment readiness from one view.", icon: BarChart3 },
  { title: "Conversations", description: "Review real customer questions, fallback moments, cited sources, and knowledge gaps without developer tooling.", icon: MessageSquareText },
  { title: "Security", description: "Keep workspace data isolated with role-based access and enterprise operating boundaries.", icon: ShieldCheck },
];

const steps = [
  { title: "Create account", description: "Start a secure Yuranix workspace for your team.", icon: UsersRound },
  { title: "Upload knowledge", description: "Add the documents your assistant should understand.", icon: UploadCloud },
  { title: "Train AI", description: "Process sources into a searchable, citation-ready knowledge layer.", icon: Network },
  { title: "Deploy widget", description: "Publish a customer-facing assistant when your team is ready.", icon: MousePointerClick },
];

const security = [
  { title: "Tenant isolation", description: "Workspace boundaries keep customer knowledge, settings, and conversations separated.", icon: Building2 },
  { title: "Enterprise security", description: "Operational controls are designed for accountable teams and production workflows.", icon: LockKeyhole },
  { title: "Source grounded", description: "Answers are tied to uploaded knowledge and reviewable citations instead of unsupported claims.", icon: FileText },
  { title: "Role based access", description: "Admins, reviewers, and team members operate with clear permission boundaries.", icon: UsersRound },
];

const pricing = [
  {
    name: "Starter",
    price: "$0",
    cadence: "to validate your first assistant",
    description: "For small teams proving the value of source-grounded AI support.",
    features: ["1 workspace", "Knowledge uploads", "Chatbot testing", "Basic analytics"],
    cta: "Get Started Free",
    href: "/knowledge",
  },
  {
    name: "Professional",
    price: "$249",
    cadence: "per month",
    description: "For growing teams deploying AI assistants across customer journeys.",
    features: ["Multiple widgets", "Conversation review", "Advanced analytics", "Team access controls"],
    cta: "Start Professional",
    href: "/widgets",
    featured: true,
  },
  {
    name: "Enterprise",
    price: "Custom",
    cadence: "for governed organisations",
    description: "For organisations that need rollout planning, security review, and dedicated support.",
    features: ["Custom deployment", "Security review", "Priority support", "Workspace governance"],
    cta: "Book Demo",
    href: "mailto:hello@yuranix.com?subject=Book%20a%20Yuranix%20demo",
  },
];

const faqs = [
  {
    question: "What does Yuranix use as its knowledge source?",
    answer: "Yuranix is designed around the documents and workspace sources your team uploads, so the assistant can answer from business-specific knowledge instead of generic content.",
  },
  {
    question: "Can we test answers before deploying?",
    answer: "Yes. Teams can test the chatbot from the dashboard, review citations, inspect fallback behaviour, and monitor conversations before publishing a widget.",
  },
  {
    question: "Does the landing page call backend APIs?",
    answer: "No. This page is a static product surface. It does not create accounts, send forms, or call backend services.",
  },
  {
    question: "How does Yuranix support enterprise teams?",
    answer: "The platform focuses on isolated workspaces, role-based access, source-grounded answers, analytics, review workflows, and controlled widget deployment.",
  },
];

const previewMetrics = [
  { label: "Answers resolved", value: 94, suffix: "%" },
  { label: "Knowledge sources", value: 128, suffix: "" },
  { label: "Open gaps", value: 7, suffix: "" },
];

export function LandingPage() {
  return (
    <main className="landingPage">
      <HeroSection />
      <TrustedBy />
      <Features />
      <HowItWorks />
      <DashboardPreview />
      <Security />
      <Pricing />
      <FAQ />
      <Footer />
    </main>
  );
}

function HeroSection() {
  return (
    <section className="landingHero" aria-labelledby="landing-hero-title">
      <LandingNav />
      <MotionBackground />
      <div className="landingHeroInner">
        <Reveal className="landingHeroCopy">
          <div className="landingPill"><Sparkles size={16} aria-hidden="true" /> Enterprise AI knowledge platform</div>
          <h1 id="landing-hero-title">Build AI Chatbots That Know Your Business</h1>
          <p>Yuranix turns your trusted business knowledge into secure, source-grounded AI assistants that can be tested, deployed, and measured from one premium workspace.</p>
          <div className="landingHeroActions">
            <Link className="landingButton landingButtonPrimary" href="/knowledge">Get Started Free <ArrowRight size={18} aria-hidden="true" /></Link>
            <a className="landingButton landingButtonSecondary" href="mailto:hello@yuranix.com?subject=Book%20a%20Yuranix%20demo">Book Demo</a>
          </div>
        </Reveal>
        <Reveal className="landingHeroVisual" delay={0.12}>
          <motion.div className="floatingLogo" animate={{ y: [0, -10, 0] }} transition={{ duration: 5, repeat: Infinity, ease: "easeInOut" }}>
            <Image src="/brand/yuranix-logo.png" alt="Yuranix" width={80} height={80} priority />
          </motion.div>
          <DashboardMockup compact />
        </Reveal>
      </div>
    </section>
  );
}

function LandingNav() {
  return (
    <nav className="landingNav" aria-label="Landing navigation">
      <Link className="landingBrand" href="/" aria-label="Yuranix home">
        <Image src="/brand/yuranix-logo.png" alt="" width={34} height={34} aria-hidden="true" />
        <span>Yuranix</span>
      </Link>
      <div className="landingNavLinks">
        <a href="#features">Features</a>
        <a href="#security">Security</a>
        <a href="#pricing">Pricing</a>
        <a href="#faq">FAQ</a>
      </div>
      <Link className="landingNavCta" href="/knowledge">Get Started</Link>
    </nav>
  );
}

function MotionBackground() {
  const reduceMotion = useReducedMotion();
  if (reduceMotion) return <div className="landingMotionGrid" aria-hidden="true" />;

  return (
    <div className="landingMotionGrid" aria-hidden="true">
      {[0, 1, 2].map((item) => (
        <motion.span
          key={item}
          animate={{ opacity: [0.18, 0.44, 0.18], scale: [1, 1.06, 1] }}
          transition={{ duration: 5 + item, repeat: Infinity, delay: item * 0.7, ease: "easeInOut" }}
        />
      ))}
    </div>
  );
}

function TrustedBy() {
  return (
    <section className="landingSection trustedSection" aria-labelledby="trusted-title">
      <p id="trusted-title" className="landingSectionKicker">Trusted by teams building governed AI experiences</p>
      <div className="trustedLogos" aria-label="Customer logos">
        {trustedLogos.map((logo) => <span key={logo}>{logo}</span>)}
      </div>
    </section>
  );
}

function Features() {
  return (
    <section id="features" className="landingSection" aria-labelledby="features-title">
      <SectionHeader kicker="Features" title="Everything required to operate a business-aware AI assistant" description="A reusable product system for knowledge, testing, deployment, review, and measurement." />
      <div className="featureGrid">
        {features.map((feature, index) => <FeatureCard key={feature.title} {...feature} delay={index * 0.04} />)}
      </div>
    </section>
  );
}

function FeatureCard({ title, description, icon: Icon, delay }: (typeof features)[number] & { delay: number }) {
  return (
    <Reveal className="landingCard featureCard" delay={delay}>
      <div className="landingIcon"><Icon size={22} aria-hidden="true" /></div>
      <h3>{title}</h3>
      <p>{description}</p>
    </Reveal>
  );
}

function HowItWorks() {
  return (
    <section className="landingSection" aria-labelledby="workflow-title">
      <SectionHeader kicker="How it works" title="From account to deployed widget in four focused steps" description="Yuranix keeps the customer journey clear without exposing implementation details." />
      <div className="workflowGrid">
        {steps.map((step, index) => {
          const Icon = step.icon;
          return (
            <Reveal className="workflowStep" key={step.title} delay={index * 0.06}>
              <span className="workflowIndex">0{index + 1}</span>
              <div className="landingIcon"><Icon size={22} aria-hidden="true" /></div>
              <h3>{step.title}</h3>
              <p>{step.description}</p>
            </Reveal>
          );
        })}
      </div>
    </section>
  );
}

function DashboardPreview() {
  return (
    <section className="landingSection dashboardPreviewSection" aria-labelledby="preview-title">
      <div>
        <SectionHeader kicker="Dashboard preview" title="A calm command center for AI operations" description="Track source health, conversations, gaps, widgets, and performance with interfaces designed for repeat use." align="left" />
        <div className="previewCallouts">
          <span><Check size={16} aria-hidden="true" /> Source health</span>
          <span><Check size={16} aria-hidden="true" /> Live review queues</span>
          <span><Check size={16} aria-hidden="true" /> Widget readiness</span>
        </div>
      </div>
      <Reveal className="dashboardPreviewFrame">
        <DashboardMockup />
      </Reveal>
    </section>
  );
}

function DashboardMockup({ compact = false }: { compact?: boolean }) {
  return (
    <div className={`dashboardMockup${compact ? " dashboardMockupCompact" : ""}`} aria-label="Yuranix dashboard preview">
      <div className="mockupTopbar">
        <div><span /> <span /> <span /></div>
        <strong>Yuranix Workspace</strong>
      </div>
      <div className="mockupBody">
        <aside className="mockupSidebar">
          {features.slice(0, 5).map((item) => <span key={item.title}>{item.title}</span>)}
        </aside>
        <div className="mockupContent">
          <div className="mockupHeader">
            <div>
              <p>AI system health</p>
              <h3>Workspace intelligence</h3>
            </div>
            <span>Healthy</span>
          </div>
          <div className="mockupMetrics">
            {previewMetrics.map((metric, index) => <AnimatedMetric key={metric.label} {...metric} delay={index * 0.1} />)}
          </div>
          <div className="mockupPanels">
            <div className="mockupChart" aria-hidden="true">
              {[42, 68, 52, 84, 74, 92].map((height, index) => <span key={index} style={{ height: `${height}%` }} />)}
            </div>
            <div className="mockupConversation">
              <span>Customer question</span>
              <p>Can I change my plan before renewal?</p>
              <span>Grounded answer</span>
              <p>Yes. The billing policy source confirms plan changes can be made before renewal.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function AnimatedMetric({ label, value, suffix, delay }: { label: string; value: number; suffix: string; delay: number }) {
  const reduceMotion = useReducedMotion();
  const display = useMemo(() => `${value}${suffix}`, [value, suffix]);

  return (
    <motion.div className="mockupMetric" initial={{ opacity: 0, y: reduceMotion ? 0 : 10 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay, duration: 0.3 }}>
      <strong>{display}</strong>
      <span>{label}</span>
    </motion.div>
  );
}

function Security() {
  return (
    <section id="security" className="landingSection securitySection" aria-labelledby="security-title">
      <SectionHeader kicker="Security" title="Built for teams that need trust before scale" description="Enterprise-grade AI requires clear boundaries, reviewable output, and accountable access." />
      <div className="securityGrid">
        {security.map((item, index) => <FeatureCard key={item.title} {...item} delay={index * 0.04} />)}
      </div>
    </section>
  );
}

function Pricing() {
  return (
    <section id="pricing" className="landingSection" aria-labelledby="pricing-title">
      <SectionHeader kicker="Pricing" title="Plans for every stage of AI adoption" description="Start focused, expand with confidence, and bring governance in when your organisation needs it." />
      <div className="pricingGrid">
        {pricing.map((plan, index) => (
          <Reveal className={`pricingCard${plan.featured ? " pricingFeatured" : ""}`} key={plan.name} delay={index * 0.06}>
            <div>
              <h3>{plan.name}</h3>
              <p>{plan.description}</p>
            </div>
            <div className="priceLine"><strong>{plan.price}</strong><span>{plan.cadence}</span></div>
            <ul>
              {plan.features.map((feature) => <li key={feature}><Check size={16} aria-hidden="true" /> {feature}</li>)}
            </ul>
            <Link className={plan.featured ? "landingButton landingButtonPrimary" : "landingButton landingButtonSecondary"} href={plan.href}>{plan.cta}</Link>
          </Reveal>
        ))}
      </div>
    </section>
  );
}

function FAQ() {
  const [open, setOpen] = useState(0);

  return (
    <section id="faq" className="landingSection faqSection" aria-labelledby="faq-title">
      <SectionHeader kicker="FAQ" title="Questions teams ask before deploying Yuranix" description="Clear answers for product, operations, support, and security stakeholders." />
      <div className="faqList">
        {faqs.map((faq, index) => {
          const expanded = open === index;
          return (
            <div className="faqItem" key={faq.question}>
              <button type="button" aria-expanded={expanded} aria-controls={`faq-panel-${index}`} onClick={() => setOpen(expanded ? -1 : index)}>
                <span>{faq.question}</span>
                <ChevronDown size={18} aria-hidden="true" />
              </button>
              <AnimatePresence initial={false}>
                {expanded ? (
                  <motion.div id={`faq-panel-${index}`} initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.22 }}>
                    <p>{faq.answer}</p>
                  </motion.div>
                ) : null}
              </AnimatePresence>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer className="landingFooter">
      <div>
        <Link className="landingBrand" href="/" aria-label="Yuranix home">
          <Image src="/brand/yuranix-logo.png" alt="" width={34} height={34} aria-hidden="true" />
          <span>Yuranix</span>
        </Link>
        <p>Enterprise AI knowledge platform for source-grounded customer assistants.</p>
      </div>
      <div className="footerLinks">
        <a href="#features">Features</a>
        <a href="#security">Security</a>
        <a href="#pricing">Pricing</a>
        <a href="mailto:hello@yuranix.com">Contact</a>
      </div>
    </footer>
  );
}

function SectionHeader({ kicker, title, description, align = "center" }: { kicker: string; title: string; description: string; align?: "left" | "center" }) {
  return (
    <Reveal className={`landingSectionHeader landingSectionHeader${align === "left" ? "Left" : "Center"}`}>
      <p className="landingSectionKicker">{kicker}</p>
      <h2>{title}</h2>
      <p>{description}</p>
    </Reveal>
  );
}

function Reveal({ children, className, delay = 0 }: { children: ReactNode; className?: string; delay?: number }) {
  const reduceMotion = useReducedMotion();
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: reduceMotion ? 0 : 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.42, delay, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.div>
  );
}



