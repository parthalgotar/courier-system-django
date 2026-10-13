import React from "react";
import { Layers } from "lucide-react";

/**
 * Reusable GroupByBar displaying active grouping chips in nesting order,
 * group counts, and Expand All / Collapse All / Clear All buttons.
 */
export default function GroupByBar({
  activeGroupBys = [],
  options = [],
  onRemoveGroup,
  onClear,
  onExpandAll,
  onCollapseAll,
  groupCount = 0,
  itemLabel = "group",
  className = "",
}) {
  if (!activeGroupBys || activeGroupBys.length === 0) return null;

  // Resolve label for a given group ID
  function getLabel(id) {
    if (!id) return "";
    if (id.includes(":")) {
      const [mainId, subId] = id.split(":");
      const mainOpt = options.find((o) => o.id === mainId);
      const subOpt = mainOpt?.subOptions?.find((s) => s.subId === subId);
      const mainLabel = mainOpt?.label || mainId;
      const subLabel = subOpt?.label || subId;
      return `${mainLabel} (${subLabel})`;
    }
    const opt = options.find((o) => o.id === id);
    return opt?.label || id;
  }

  return (
    <div
      className={`flex flex-wrap items-center justify-between gap-2 mb-3 px-3.5 py-2 bg-paper/60 border border-paper-line rounded-lg text-xs ${className}`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-ink-soft flex items-center gap-1 font-medium">
          <Layers size={13} className="text-[#714B67]" />
          <span>Grouped by:</span>
        </span>

        {activeGroupBys.map((gId, idx) => {
          const label = getLabel(gId);
          return (
            <span
              key={gId}
              className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-[#714B67]/10 text-[#714B67] font-medium border border-[#714B67]/20"
            >
              <span className="font-mono font-bold text-[10px]">{idx + 1}.</span>
              <span>{label}</span>
              <button
                type="button"
                onClick={() => onRemoveGroup(gId)}
                className="ml-0.5 hover:text-red-600 transition-colors font-bold text-sm leading-none"
                title={`Remove ${label} grouping`}
                aria-label={`Remove ${label}`}
              >
                ×
              </button>
            </span>
          );
        })}

        {groupCount > 0 && (
          <span className="text-ink-faint">
            ({groupCount} {groupCount === 1 ? itemLabel : `${itemLabel}s`})
          </span>
        )}
      </div>

      <div className="flex items-center gap-2">
        {onExpandAll && (
          <button
            type="button"
            onClick={onExpandAll}
            className="text-xs text-freight hover:text-freight-dark font-mono uppercase tracking-wide hover:underline transition-colors"
          >
            Expand All
          </button>
        )}
        {onExpandAll && onCollapseAll && <span className="text-paper-line">|</span>}
        {onCollapseAll && (
          <button
            type="button"
            onClick={onCollapseAll}
            className="text-xs text-freight hover:text-freight-dark font-mono uppercase tracking-wide hover:underline transition-colors"
          >
            Collapse All
          </button>
        )}
        {onClear && (
          <>
            <span className="text-paper-line">|</span>
            <button
              type="button"
              onClick={onClear}
              className="text-xs text-ink-soft hover:text-red-500 font-mono uppercase tracking-wide hover:underline transition-colors"
            >
              Clear All
            </button>
          </>
        )}
      </div>
    </div>
  );
}
