import type { Metadata } from "next";

import { PricingPage } from "../../components/pricing/pricing-page";

export const metadata: Metadata = {
  title: "Pricing - Conversa",
  description: "Plans for every stage of AI adoption, all starting with a 14-day free trial.",
};

export default function Page() {
  return <PricingPage />;
}
