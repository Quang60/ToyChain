import './BranchCompass.css';

const directions = [
  { node: 'BAC', label: 'BẮC', name: 'Bắc', angle: 0, x: 120, y: 16 },
  { node: 'DONG', label: 'ĐÔNG', name: 'Đông', angle: 90, x: 220, y: 124 },
  { node: 'NAM', label: 'NAM', name: 'Nam', angle: 180, x: 120, y: 236 },
  { node: 'TAY', label: 'TÂY', name: 'Tây', angle: 270, x: 20, y: 124 },
] as const;

export default function BranchCompass({ node }: { node: string }) {
  const direction = directions.find(item => item.node === node);
  const description = direction
    ? `La bàn chỉ hướng ${direction.name}, chi nhánh đang chọn.`
    : 'Trung tâm kết nối bốn chi nhánh, không có kim chỉ hướng.';

  return (
    <figure className="branch-compass">
      <svg viewBox="0 0 240 248" role="img" aria-label={description}>
        <circle className="compass-ring" cx="120" cy="120" r="82" />
        <circle className="compass-ring compass-inner-ring" cx="120" cy="120" r="65" />
        {Array.from({ length: 16 }, (_, index) => (
          <path
            key={index}
            className="compass-tick"
            d={index % 4 === 0 ? 'M120 38V49' : 'M120 38V43'}
            transform={`rotate(${index * 22.5} 120 120)`}
          />
        ))}
        {directions.map(item => (
          <text
            key={item.node}
            className={`compass-direction${direction?.node === item.node ? ' is-active' : ''}`}
            x={item.x}
            y={item.y}
            textAnchor="middle"
          >
            {item.label}
          </text>
        ))}
        {direction ? (
          <g className="compass-needle" transform={`rotate(${direction.angle} 120 120)`}>
            <path className="compass-needle-tail" d="M120 161L109 121L120 115L131 121Z" />
            <path className="compass-needle-tip" d="M120 55L133 127L120 118L107 127Z" />
            <circle className="compass-pivot" cx="120" cy="120" r="5" />
          </g>
        ) : (
          <g className="compass-center">
            <path d="M120 79V101M120 139V161M79 120H101M139 120H161" />
            <circle className="compass-center-ring" cx="120" cy="120" r="19" />
            <circle className="compass-center-dot" cx="120" cy="120" r="6" />
            <circle className="compass-center-dot" cx="120" cy="77" r="3" />
            <circle className="compass-center-dot" cx="163" cy="120" r="3" />
            <circle className="compass-center-dot" cx="120" cy="163" r="3" />
            <circle className="compass-center-dot" cx="77" cy="120" r="3" />
          </g>
        )}
      </svg>
      <figcaption>{direction ? `Chi nhánh ${direction.name}` : 'Trung tâm'}</figcaption>
    </figure>
  );
}
