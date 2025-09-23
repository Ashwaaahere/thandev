// components/News/RightSidebar.tsx
import type { Item } from "@/components/types";
import PinnedTimeline from "./PinnedTimeline";
import TopSourcesBox from "./TopSourcesBox";
import QuickFiltersBox from "./QuickFiltersBox";
import SubscribeCard from "./SubscribeCard";

type Props = {
  className?: string;
  pinned?: Item[];
  latest?: Item[];
};

export default function RightSidebar({
  className = "",
  pinned = [],
  latest = [],
}: Props) {
  return (
    // hidden on small screens; becomes a true sidebar on lg+
    <aside className={`hidden lg:block ${className}`}>
      {/* keep the column fixed and independent of page scroll height */}
      <div className="sticky top-24">
        {/* independent scroll area that fits viewport height minus header spacing */}
        <div
          className="
            flex flex-col gap-4
            max-h-[calc(100vh-120px)]
            overflow-y-auto pr-1

            [scrollbar-width:thin]
            [scrollbar-color:theme(colors.slate.500)_transparent]
          "
        >
          {/* 1) Pinned timeline (top 5) */}
          <PinnedTimeline items={(pinned ?? []).slice(0, 5)} />

          {/* 2) Top sources meter */}
          <TopSourcesBox items={latest ?? []} />

          {/* 3) Quick filters */}
          <QuickFiltersBox items={latest ?? []} />

          {/* 4) Subscribe */}
          <SubscribeCard />
        </div>
      </div>
    </aside>
  );
}
