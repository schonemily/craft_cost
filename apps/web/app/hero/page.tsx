import { HeroGeometric } from "@/components/ui/shape-landing-hero";

export const metadata = {
  title: "Hero Preview",
  description: "Geometric hero preview",
};

export default function HeroPage() {
  return (
    <div className="min-h-screen">
      <HeroGeometric />
    </div>
  );
}
