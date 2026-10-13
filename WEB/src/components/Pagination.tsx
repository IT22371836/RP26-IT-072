import React from 'react';
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-react';

interface PaginationProps {
  currentPage: number;
  totalPages: number;
  totalItems: number;
  itemsPerPage: number;
  onPageChange: (page: number) => void;
  itemName?: string;
}

export const Pagination: React.FC<PaginationProps> = ({
  currentPage,
  totalPages,
  totalItems,
  itemsPerPage,
  onPageChange,
  itemName = 'items'
}) => {
  if (totalItems === 0 || totalPages <= 1) return null;

  const startItem = (currentPage - 1) * itemsPerPage + 1;
  const endItem = Math.min(currentPage * itemsPerPage, totalItems);
  const pages: (number | 'ellipsis')[] = [];

  if (totalPages <= 7) {
    for (let page = 1; page <= totalPages; page += 1) pages.push(page);
  } else if (currentPage <= 3) {
    pages.push(1, 2, 3, 4, 'ellipsis', totalPages);
  } else if (currentPage >= totalPages - 2) {
    pages.push(1, 'ellipsis', totalPages - 3, totalPages - 2, totalPages - 1, totalPages);
  } else {
    pages.push(1, 'ellipsis', currentPage - 1, currentPage, currentPage + 1, 'ellipsis', totalPages);
  }

  const iconButtonStyle: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '36px',
    height: '36px',
    borderRadius: '10px',
    border: '1px solid #cbd5e1',
    background: '#ffffff'
  };

  return (
    <div className="glass-panel" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px', padding: '14px 18px', border: '1px solid rgba(39, 98, 33, 0.25)', background: 'rgba(255, 255, 255, 0.75)' }}>
      <div style={{ fontSize: '0.88rem', color: 'var(--text-muted)' }}>
        Showing <strong>{startItem}–{endItem}</strong> of <strong style={{ color: '#276221' }}>{totalItems}</strong> {itemName} · Page <strong>{currentPage}</strong> of <strong>{totalPages}</strong>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
        <button type="button" onClick={() => onPageChange(1)} disabled={currentPage === 1} aria-label="First page" style={iconButtonStyle}>
          <ChevronsLeft size={16} />
        </button>
        <button type="button" onClick={() => onPageChange(currentPage - 1)} disabled={currentPage === 1} aria-label="Previous page" style={iconButtonStyle}>
          <ChevronLeft size={16} />
        </button>
        {pages.map((page, index) => page === 'ellipsis' ? (
          <span key={`ellipsis-${index}`} style={{ padding: '0 4px', color: '#94a3b8' }}>…</span>
        ) : (
          <button
            key={page}
            type="button"
            onClick={() => onPageChange(page)}
            aria-current={page === currentPage ? 'page' : undefined}
            style={{ ...iconButtonStyle, background: page === currentPage ? '#276221' : '#ffffff', color: page === currentPage ? '#ffffff' : 'var(--text-main)', fontWeight: page === currentPage ? 700 : 500 }}
          >
            {page}
          </button>
        ))}
        <button type="button" onClick={() => onPageChange(currentPage + 1)} disabled={currentPage === totalPages} aria-label="Next page" style={iconButtonStyle}>
          <ChevronRight size={16} />
        </button>
        <button type="button" onClick={() => onPageChange(totalPages)} disabled={currentPage === totalPages} aria-label="Last page" style={iconButtonStyle}>
          <ChevronsRight size={16} />
        </button>
      </div>
    </div>
  );
};
