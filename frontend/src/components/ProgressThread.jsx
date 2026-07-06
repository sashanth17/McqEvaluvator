import { useLocation } from 'react-router-dom';
import { cn } from '../lib/utils';

export default function ProgressThread() {
  const location = useLocation();
  const path = location.pathname;

  let progress = "0%";
  if (path === '/upload') progress = "33%";
  else if (path === '/interview') progress = "66%";
  else if (path === '/report') progress = "100%";

  return (
    <div className="fixed left-0 top-0 bottom-0 w-1 bg-surface/10 z-50">
      <div 
        className="w-full bg-accent transition-all duration-700 ease-in-out"
        style={{ height: progress }}
      />
    </div>
  );
}
