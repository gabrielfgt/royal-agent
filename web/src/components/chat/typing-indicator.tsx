export function TypingIndicator() {
  return (
    <div className="flex w-fit items-center gap-1 rounded-2xl rounded-tl-sm bg-bubble-agent px-4 py-3 shadow-xs" aria-label="Sofia está digitando">
      {[0, 150, 300].map((delay) => (
        <span key={delay} className="size-2 animate-typing rounded-full bg-muted-foreground" style={{ animationDelay: `${delay}ms` }} />
      ))}
    </div>
  );
}
