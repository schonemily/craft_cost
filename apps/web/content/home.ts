export const homeContent = {
  appName: "craft_cost",
  hero: {
    title: "Spend better. Simple financial clarity.",
    subtitle:
      "Use Craft Cost to upload your transactions, explore spend by category, and discover savings opportunities.",
    images: [
      "https://images.unsplash.com/photo-1554224155-1696413565d3?q=80&w=1600&auto=format&fit=crop",
      "https://images.unsplash.com/photo-1553729459-efe14ef6055d?q=80&w=1600&auto=format&fit=crop",
      "https://images.unsplash.com/photo-1518186285589-2f7649de83e0?q=80&w=1600&auto=format&fit=crop",
    ],
    ctaPrimary: { label: "Upload CSV", href: "/upload" },
    ctaSecondary: { label: "Explore Spend", href: "/spend" },
  },
  metrics: [
    { label: "CSV files uploaded", value: "12" },
    { label: "Categories tracked", value: "18" },
    { label: "Insights generated", value: "42" },
    { label: "Debt tools", value: "Active" },
  ],
  quick: [
    {
      title: "Upload CSV",
      description: "Import bank statements and start analyzing.",
      href: "/upload",
    },
    {
      title: "View Spend",
      description: "Browse by category and time period.",
      href: "/spend",
    },
    {
      title: "See Suggestions",
      description: "Find savings and smarter habits.",
      href: "/suggestions",
    },
    {
      title: "Debt tools",
      description: "Plan payoff and track balances.",
      href: "/debt",
    },
  ],
  how: {
    headline: "How it works",
    steps: [
      { title: "1. Upload", description: "Add your CSVs from your bank." },
      { title: "2. Categorize", description: "Review categories and totals." },
      { title: "3. Discover", description: "See insights and suggestions." },
      { title: "4. Act", description: "Make changes and track progress." },
    ],
  },
  why: {
    headline: "Why choose us",
    bullets: [
      "Automatic reminders and tips",
      "Clear analytics and visual breakdowns",
      "Simple CSV pipeline — no lock‑in",
      "Privacy‑first, local control",
    ],
  },
  testimonials: [
    {
      quote: "Craft Cost helped me find wasteful subscriptions and save over $120/month.",
      author: "Alex R.",
      role: "Freelancer",
    },
    {
      quote: "The category breakdowns and suggestions are exactly what I needed.",
      author: "Priya S.",
      role: "Product Manager",
    },
  ],
  logos: [
    { alt: "Acme", src: "/logos/logo-1.svg" },
    { alt: "Nimbus", src: "/logos/logo-2.svg" },
    { alt: "Nova", src: "/logos/logo-3.svg" },
    { alt: "Pioneer", src: "/logos/logo-4.svg" },
  ],
};

export type HomeContent = typeof homeContent;
