// components/News/RightSidebar.tsx
import type { Item } from "@/components/types";
import PinnedTimeline from "./PinnedTimeline";
import TopSourcesBox from "./TopSourcesBox";
import QuickFiltersBox from "./QuickFiltersBox";
import SubscribeCard from "./SubscribeCard";
import AdditionalContent from "./AdditionalContent";

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
    <aside className={`hidden lg:block ${className} space-y-6`}>
      {/* keep the column fixed and independent of page scroll height */}
      <div className="sticky top-24">
        {/* independent scroll area that fits viewport height minus header spacing */}
        <div
          className="
            flex flex-col gap-6
            relative z-10
            pr-1
          "
        >
          {/* 1) Pinned timeline (top 5) - natural height */}
          <div className="top-5-container">
            <PinnedTimeline items={(pinned ?? []).slice(0, 5)} />
          </div>

          {/* 2) Top sources meter */}
          <TopSourcesBox />

          {/* 3) Quick filters */}
          <QuickFiltersBox />

          {/* 4) Subscribe - always visible at bottom */}
          <SubscribeCard />

          {/* 5) Additional content to fill space */}
          <AdditionalContent />
        </div>
      </div>
    </aside>
  );
}
