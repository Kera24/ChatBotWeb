import { describe, expect, it } from "vitest";

import { render, screen } from "../../test/test-utils";
import { BrandingCard } from "./branding-card";

describe("BrandingCard", () => {
  it("explains that branding is managed under Widget Builder and links out", () => {
    render(<BrandingCard />);

    expect(screen.getByText(/stored per assistant/i)).toBeTruthy();
    expect(screen.getByRole("link", { name: /Manage widget configuration/ }).getAttribute("href")).toBe("/widgets");
    expect(screen.getByRole("link", { name: /Open chatbot preview/ }).getAttribute("href")).toBe("/chatbot");
  });
});
