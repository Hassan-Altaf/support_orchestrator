import { MessageSquareText } from "lucide-react";
import { Card } from "@/components/ui/Card";

export function CustomerResponseCard({ text }: { text: string }) {
  return (
    <Card
      title={
        <span className="inline-flex items-center gap-1.5">
          <MessageSquareText className="h-4 w-4 text-emerald-600" /> Customer reply
        </span>
      }
      subtitle="What the customer would see"
      accent="green"
    >
      <blockquote className="border-l-2 border-emerald-300 pl-4 text-sm leading-relaxed text-slate-800">
        {text}
      </blockquote>
    </Card>
  );
}
