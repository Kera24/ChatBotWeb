# Design System Direction

Version: 0.1
Status: Draft

## Design goal

Create a polished enterprise SaaS interface that feels trustworthy, calm, fast, and professional.

The product should feel closer to Linear, Vercel, Notion, and the OpenAI dashboard than a generic chatbot template.

## Design principles

1. Clarity over decoration.
2. Calm interface for complex AI workflows.
3. Strong information hierarchy.
4. Fast interactions and minimal waiting.
5. Accessible by default.
6. Client branding should be configurable but controlled.
7. AI behaviour should be transparent through sources, status, and confidence indicators.

## Visual personality

- Minimal
- Enterprise-grade
- Clean
- Modern
- Technical but approachable
- Professional enough for colleges and service businesses

## Colour direction

Use a light SaaS interface with neutral backgrounds, white cards, dark readable text, blue primary actions, green success states, amber warnings, and red destructive actions.

## Typography

Recommended fonts:

- Inter
- Geist
- IBM Plex Sans

## Layout principles

- Sidebar navigation for dashboards
- Workspace switcher
- Clear page headers
- Card-based sections
- Tables for operational data
- Empty states that explain next steps
- Progressive disclosure for advanced settings

## Main screens

### Super-admin dashboard

- Organisations
- Workspaces
- Usage
- System health
- Model settings

### Client dashboard

- Overview
- Knowledge base
- Chatbot configuration
- Chat history
- Unanswered questions
- Analytics
- Users and roles
- Settings

### Knowledge base screen

Must show document title, source type, status, update time, processing errors, and available actions.

### Chatbot configuration screen

Must allow bot name, welcome message, logo, brand colour, suggested questions, fallback contact, and widget install instructions.

### Analytics screen

Must show conversations, messages, unanswered questions, common topics, documents used, feedback score, and estimated AI cost.

## Widget design

The website widget should be lightweight, fast, mobile responsive, brandable, and easy to embed.

Widget states:

- Closed launcher
- Welcome screen
- Chat screen
- Loading answer
- Answer with citations
- Low-confidence fallback
- Contact capture form

## Motion design

Use subtle motion only. Avoid excessive animation.

## Accessibility

Minimum requirements:

- Keyboard navigation
- Focus states
- Good colour contrast
- Screen-reader labels
- Responsive layouts
- Clear errors and status messages

## Component direction

Use shadcn/ui as the base component library and customise it into a professional SaaS design system.
