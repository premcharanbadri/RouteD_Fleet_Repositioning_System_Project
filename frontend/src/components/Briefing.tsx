interface Props {
  text: string;
  usedAi: boolean;
  title?: string;
}

export function Briefing({ text, usedAi, title = "Dispatch Briefing" }: Props) {
  return (
    <section className="panel briefing">
      <h2>
        {title}
        <span className={`tag ${usedAi ? "ai" : "rule"}`}>{usedAi ? "AI" : "rule-based"}</span>
      </h2>
      <p>{text}</p>
    </section>
  );
}
