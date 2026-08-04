"use client";

import { motion, useReducedMotion } from "framer-motion";
import Image from "next/image";
import Link from "next/link";
import type { ReactNode } from "react";
import { ArrowRight, Check, Sparkles } from "lucide-react";

export type PricingTier = {
  key: string;
  name: string;
  price: string;
  cadence: string;
  description: string;
  features: string[];
  cta: string;
  href: string;
  featured?: true;
};

export const PRICING_TIERS: PricingTier[] = [
  {
    key: "starter",
    name: "Starter",
    price: "$0",
    cadence: "free 14-day trial, then $0",
    description: "For small teams proving the value of source-grounded AI support.",
    features: ["1 assistant", "Knowledge uploads", "Chatbot testing", "Basic analytics"],
    cta: "Start free trial",
    href: "/register",
  },
  {
    key: "professional",
    name: "Professional",
    price: "$249",
    cadence: "per month, after a 14-day trial",
    description: "For growing teams deploying AI assistants across customer journeys.",
    features: ["Up to 10 assistants", "Conversation review", "Advanced analytics", "Team access controls"],
    cta: "Start free trial",
    href: "/register",
    featured: true,
  },
  {
    key: "enterprise",
    name: "Enterprise",
    price: "Custom",
    cadence: "for governed organisations",
    description: "For organisations that need rollout planning, security review, and dedicated support.",
    features: ["Unlimited assistants", "Security review", "Priority support", "Workspace governance"],
    cta: "Book a demo",
    href: "mailto:hello@yoranix.com?subject=Book%20a%20Conversa%20demo",
  },
];

export function PricingPage() {
  return (
    <div className="landingPage">
      <PricingNav />
      <main>
        <section className="landingSection" aria-labelledby="pricing-hero-title">
          <Reveal className="landingSectionHeader landingSectionHeaderCenter">
            <p className="landingSectionKicker">Pricing</p>
            <h1 id="pricing-hero-title">Plans for every stage of AI adoption</h1>
            <p>Start focused, expand with confidence, and bring governance in when your organisation needs it.</p>
            <div className="landingPill"><Sparkles size={16} aria-hidden="true" /> Every plan starts with a 14-day free trial &mdash; no credit card required</div>
          </Reveal>
          <div className="pricingGrid">
            {PRICING_TIERS.map((plan, index) => (
              <Reveal className={`pricingCard${plan.featured ? " pricingFeatured" : ""}`} key={plan.key} delay={index * 0.06}>
                <div>
                  <h3>{plan.name}</h3>
                  <p>{plan.description}</p>
                </div>
                <div className="priceLine">
                  <strong>{plan.price}</strong>
                  <span>{plan.cadence}</span>
                </div>
                <ul>
                  {plan.features.map((feature) => (
                    <li key={feature}>
                      <Check size={16} aria-hidden="true" /> {feature}
                    </li>
                  ))}
                </ul>
                <Link
                  className={plan.featured ? "landingButton landingButtonPrimary" : "landingButton landingButtonSecondary"}
                  href={plan.href}
                >
                  {plan.cta}
                  {!plan.href.startsWith("mailto:") ? <ArrowRight size={16} aria-hidden="true" /> : null}
                </Link>
              </Reveal>
            ))}
          </div>
        </section>
      </main>
      <PricingFooter />
    </div>
  );
}

function PricingNav() {
  return (
    <nav className="landingNav" aria-label="Pricing navigation">
      <Link className="landingBrand" href="/" aria-label="Conversa home">
        <Image src="/brand/conversa-icon.svg" alt="" width={34} height={34} aria-hidden="true" />
        <span>Conversa</span>
      </Link>
      <div className="landingNavLinks">
        <Link href="/#features">Features</Link>
        <Link href="/#security">Security</Link>
        <Link href="/#faq">FAQ</Link>
      </div>
      <div className="landingNavActions">
        <Link className="landingLoginLink" href="/login">Log in</Link>
        <Link className="landingNavCta" href="/register">Get Started</Link>
      </div>
    </nav>
  );
}

function PricingFooter() {
  return (
    <footer className="landingFooter">
      <div>
        <Link className="landingBrand" href="/" aria-label="Conversa home">
          <Image src="/brand/conversa-icon.svg" alt="" width={34} height={34} aria-hidden="true" />
          <span>Conversa</span>
        </Link>
        <p>Enterprise AI knowledge platform for source-grounded customer assistants.</p>
      </div>
      <div className="footerLinks">
        <Link href="/">Home</Link>
        <a href="mailto:hello@yoranix.com">Contact</a>
      </div>
    </footer>
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
