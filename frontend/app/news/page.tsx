import { Suspense } from 'react';
import NewsList from './NewsList';
import Loading from './loading';

export default function NewsPage() {
  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto max-w-6xl px-4 py-8">
        <h1 className="text-2xl font-semibold mb-6">Latest News</h1>
        <Suspense fallback={<Loading />}>
          {/* NewsList (server) suspends while fetching → shows Loading */}
          <NewsList />
        </Suspense>
      </div>
    </main>
  );
}
