export default function TopicTags({ topics }) {
  if (!topics || topics.length === 0) return null;

  return (
    <div className="mt-8">
      <h3 className="font-serif text-xl text-surface mb-4">Topics to revisit</h3>
      <div className="flex flex-wrap gap-3">
        {topics.map((topic, index) => {
          // Calculate dynamic size based on count (simple tag-cloud effect)
          const isLarge = topic.count > 2;
          const isMedium = topic.count === 2;
          
          return (
            <span 
              key={index}
              className={`inline-flex items-center justify-center rounded-full bg-surface/10 border border-surface/20 text-surface font-medium transition-all hover:bg-surface/20
                ${isLarge ? 'text-lg px-5 py-2.5' : isMedium ? 'text-base px-4 py-2' : 'text-sm px-3 py-1.5'}
              `}
            >
              {topic.name}
            </span>
          );
        })}
      </div>
    </div>
  );
}
