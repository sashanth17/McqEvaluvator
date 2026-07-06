import QuestionCard from './QuestionCard';

export default function QuestionBreakdownList({ breakdown }) {
  if (!breakdown || breakdown.length === 0) return null;

  return (
    <div className="flex flex-col gap-4">
      {breakdown.map((q, index) => (
        <QuestionCard key={q.id || index} question={q} number={(index + 1).toString().padStart(2, '0')} />
      ))}
    </div>
  );
}
