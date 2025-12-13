'use client';

import { useState, useEffect } from 'react';
import { useSession } from 'next-auth/react';
import NewsClientWrapper from './NewsClientWrapper';
import RightSidebar from './RightSidebar';
import NewsStats from './NewsStats';
import { thandevFetchJSON } from '@/lib/thandevApi';

type NewsItem = {
  id: string;
  title: string;
  url: string;
  source: string;
  publishedAt: string;
  summary: string;
  category: 'cyber' | 'ai' | 'tech';
  image?: string | null;
  certified: boolean;
};

type FindingListItem = {
  cve_id?: string | null;
};

type FindingsResponse = {
  items: FindingListItem[];
  total: number;
};

export default function NewsPageClient() {
  const { data: session, status: sessionStatus } = useSession();
  const [news, setNews] = useState<NewsItem[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [cveIds, setCveIds] = useState<Set<string>>(new Set());
  const [cveCounts, setCveCounts] = useState<Map<string, number>>(new Map());
  const [findingsLoading, setFindingsLoading] = useState(false);

  // Fetch findings to extract CVE IDs
  useEffect(() => {
    async function loadFindings() {
      if (sessionStatus !== 'authenticated' || !session) return;
      
      setFindingsLoading(true);
      try {
        const data = await thandevFetchJSON<FindingsResponse>(
          '/api/findings?limit=50',
          session
        );
        
        // Extract CVE IDs and count occurrences
        const cveSet = new Set<string>();
        const cveMap = new Map<string, number>();
        
        data.items.forEach((finding) => {
          if (finding.cve_id) {
            const cve = finding.cve_id.trim().toUpperCase();
            cveSet.add(cve);
            cveMap.set(cve, (cveMap.get(cve) || 0) + 1);
          }
        });
        
        setCveIds(cveSet);
        setCveCounts(cveMap);
      } catch (e) {
        console.error('Error loading findings for CVE matching:', e);
        // Silently fail - CVE matching is optional
      } finally {
        setFindingsLoading(false);
      }
    }
    
    loadFindings();
  }, [sessionStatus, session]);

  const handleStatsUpdate = (newsItems: NewsItem[], total: number) => {
    setNews(newsItems);
    setTotalCount(total);
    setLoading(false);
  };

  return (
    <>
      {/* Stats bar */}
      <NewsStats news={news} totalCount={totalCount} loading={loading} />

      {/* FEED + RIGHT SIDEBAR */}
      <section className="grid grid-cols-1 gap-8 lg:grid-cols-4">
        <div className="lg:col-span-3 space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-bold text-[var(--fg)]">Security News Feed</h2>
            <div className="flex items-center gap-2 text-sm text-[var(--muted)]">
              <div className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
              <span>Live updates</span>
            </div>
          </div>
          <NewsClientWrapper 
            initialNews={[]} 
            totalCount={0} 
            onStatsUpdate={handleStatsUpdate}
            cveIds={cveIds}
          />
        </div>
        <aside className="lg:col-span-1">
          <RightSidebar 
            pinned={news.slice(0, 5)} 
            latest={news}
            cveCounts={cveCounts}
            loading={findingsLoading}
          />
        </aside>
      </section>
    </>
  );
}

            cveMap.set(cve, (cveMap.get(cve) || 0) + 1);
          }
        });
        
        setCveIds(cveSet);
        setCveCounts(cveMap);
      } catch (e) {
        console.error('Error loading findings for CVE matching:', e);
        // Silently fail - CVE matching is optional
      } finally {
        setFindingsLoading(false);
      }
    }
    
    loadFindings();
  }, [sessionStatus, session]);

  const handleStatsUpdate = (newsItems: NewsItem[], total: number) => {
    setNews(newsItems);
    setTotalCount(total);
    setLoading(false);
  };

  return (
    <>
      {/* Stats bar */}
      <NewsStats news={news} totalCount={totalCount} loading={loading} />

      {/* FEED + RIGHT SIDEBAR */}
      <section className="grid grid-cols-1 gap-8 lg:grid-cols-4">
        <div className="lg:col-span-3 space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-bold text-[var(--fg)]">Security News Feed</h2>
            <div className="flex items-center gap-2 text-sm text-[var(--muted)]">
              <div className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
              <span>Live updates</span>
            </div>
          </div>
          <NewsClientWrapper 
            initialNews={[]} 
            totalCount={0} 
            onStatsUpdate={handleStatsUpdate}
            cveIds={cveIds}
          />
        </div>
        <aside className="lg:col-span-1">
          <RightSidebar 
            pinned={news.slice(0, 5)} 
            latest={news}
            cveCounts={cveCounts}
            loading={findingsLoading}
          />
        </aside>
      </section>
    </>
  );
}

            cveMap.set(cve, (cveMap.get(cve) || 0) + 1);
          }
        });
        
        setCveIds(cveSet);
        setCveCounts(cveMap);
      } catch (e) {
        console.error('Error loading findings for CVE matching:', e);
        // Silently fail - CVE matching is optional
      } finally {
        setFindingsLoading(false);
      }
    }
    
    loadFindings();
  }, [sessionStatus, session]);

  const handleStatsUpdate = (newsItems: NewsItem[], total: number) => {
    setNews(newsItems);
    setTotalCount(total);
    setLoading(false);
  };

  return (
    <>
      {/* Stats bar */}
      <NewsStats news={news} totalCount={totalCount} loading={loading} />

      {/* FEED + RIGHT SIDEBAR */}
      <section className="grid grid-cols-1 gap-8 lg:grid-cols-4">
        <div className="lg:col-span-3 space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-bold text-[var(--fg)]">Security News Feed</h2>
            <div className="flex items-center gap-2 text-sm text-[var(--muted)]">
              <div className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
              <span>Live updates</span>
            </div>
          </div>
          <NewsClientWrapper 
            initialNews={[]} 
            totalCount={0} 
            onStatsUpdate={handleStatsUpdate}
            cveIds={cveIds}
          />
        </div>
        <aside className="lg:col-span-1">
          <RightSidebar 
            pinned={news.slice(0, 5)} 
            latest={news}
            cveCounts={cveCounts}
            loading={findingsLoading}
          />
        </aside>
      </section>
    </>
  );
}

            cveMap.set(cve, (cveMap.get(cve) || 0) + 1);
          }
        });
        
        setCveIds(cveSet);
        setCveCounts(cveMap);
      } catch (e) {
        console.error('Error loading findings for CVE matching:', e);
        // Silently fail - CVE matching is optional
      } finally {
        setFindingsLoading(false);
      }
    }
    
    loadFindings();
  }, [sessionStatus, session]);

  const handleStatsUpdate = (newsItems: NewsItem[], total: number) => {
    setNews(newsItems);
    setTotalCount(total);
    setLoading(false);
  };

  return (
    <>
      {/* Stats bar */}
      <NewsStats news={news} totalCount={totalCount} loading={loading} />

      {/* FEED + RIGHT SIDEBAR */}
      <section className="grid grid-cols-1 gap-8 lg:grid-cols-4">
        <div className="lg:col-span-3 space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-bold text-[var(--fg)]">Security News Feed</h2>
            <div className="flex items-center gap-2 text-sm text-[var(--muted)]">
              <div className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
              <span>Live updates</span>
            </div>
          </div>
          <NewsClientWrapper 
            initialNews={[]} 
            totalCount={0} 
            onStatsUpdate={handleStatsUpdate}
            cveIds={cveIds}
          />
        </div>
        <aside className="lg:col-span-1">
          <RightSidebar 
            pinned={news.slice(0, 5)} 
            latest={news}
            cveCounts={cveCounts}
            loading={findingsLoading}
          />
        </aside>
      </section>
    </>
  );
}
