import { ExternalLink } from "lucide-react";
import Link from "next/link";

export function BrandingCard() {
  return (
    <section className="settingsPanel" aria-labelledby="branding-settings-title">
      <div className="settingsPanelHeader">
        <div>
          <p className="sectionKicker">Branding and chatbot</p>
          <h3 id="branding-settings-title">Widget-owned configuration</h3>
        </div>
      </div>
      <p>Client-facing chatbot name, colours, logo, welcome message, fallback contact, privacy links, suggestions, citations, and conversation behaviour are stored per assistant, not at the workspace level. Manage them from Widget Builder.</p>
      <div className="settingsLinkList">
        <Link className="smallButton" href="/widgets">Manage widget configuration<ExternalLink size={13} aria-hidden="true" /></Link>
        <Link className="smallButton" href="/chatbot">Open chatbot preview<ExternalLink size={13} aria-hidden="true" /></Link>
      </div>
    </section>
  );
}
