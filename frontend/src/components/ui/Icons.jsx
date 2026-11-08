import React from "react";

export function Icon({ d, className = "w-5 h-5", size = 20, ...props }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      {...props}
    >
      {Array.isArray(d) ? d.map((path, idx) => <path key={idx} d={path} />) : <path d={d} />}
    </svg>
  );
}

export const Icons = {
  Overview: (props) => (
    <Icon
      d={[
        "M3 3h7v7H3z",
        "M14 3h7v7h-7z",
        "M14 14h7v7h-7z",
        "M3 14h7v7H3z",
      ]}
      {...props}
    />
  ),
  Appraisal: (props) => (
    <Icon
      d={[
        "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z",
        "M14 2v6h6",
        "M16 13H8",
        "M16 17H8",
        "M10 9H8",
      ]}
      {...props}
    />
  ),
  Research: (props) => (
    <Icon
      d={[
        "M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20",
        "M6 6h10",
        "M6 10h10",
      ]}
      {...props}
    />
  ),
  Teaching: (props) => (
    <Icon
      d={[
        "M22 10v6M2 10l10-5 10 5-10 5z",
        "M6 12v5c3 3 9 3 12 0v-5",
      ]}
      {...props}
    />
  ),
  Schedule: (props) => (
    <Icon
      d={[
        "M8 2v4",
        "M16 2v4",
        "M3 10h18",
        "M5 4h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z",
      ]}
      {...props}
    />
  ),
  Admin: (props) => (
    <Icon
      d={[
        "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2",
        "M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z",
        "M19 11l2 2 4-4",
      ]}
      {...props}
    />
  ),
  Evidence: (props) => (
    <Icon
      d={[
        "M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48",
      ]}
      {...props}
    />
  ),
  Profile: (props) => (
    <Icon
      d={[
        "M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2",
        "M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z",
      ]}
      {...props}
    />
  ),
  Review: (props) => (
    <Icon
      d={[
        "M9 11l3 3L22 4",
        "M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11",
      ]}
      {...props}
    />
  ),
  Users: (props) => (
    <Icon
      d={[
        "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2",
        "M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z",
        "M23 21v-2a4 4 0 0 0-3-3.87",
        "M16 3.13a4 4 0 0 1 0 7.75",
      ]}
      {...props}
    />
  ),
  ChevronRight: (props) => <Icon d="M9 18l6-6-6-6" {...props} />,
  ChevronDown: (props) => <Icon d="M6 9l6 6 6-6" {...props} />,
  ExternalLink: (props) => (
    <Icon
      d={[
        "M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6",
        "M15 3h6v6",
        "M10 14L21 3",
      ]}
      {...props}
    />
  ),
  Menu: (props) => <Icon d="M3 12h18M3 6h18M3 18h18" {...props} />,
  Close: (props) => <Icon d="M18 6L6 18M6 6l12 12" {...props} />,
  LogOut: (props) => (
    <Icon
      d={[
        "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4",
        "M16 17l5-5-5-5",
        "M21 12H9",
      ]}
      {...props}
    />
  ),
  Check: (props) => <Icon d="M20 6L9 17l-5-5" {...props} />,
  Clock: (props) => <Icon d={["M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z", "M12 6v6l4 2"]} {...props} />,
  Alert: (props) => (
    <Icon
      d={[
        "M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z",
        "M12 9v4",
        "M12 17h.01",
      ]}
      {...props}
    />
  ),
  Plus: (props) => <Icon d="M12 5v14M5 12h14" {...props} />,
  Edit: (props) => (
    <Icon
      d={[
        "M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7",
        "M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z",
      ]}
      {...props}
    />
  ),
  Trash: (props) => (
    <Icon
      d={[
        "M3 6h18",
        "M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2",
      ]}
      {...props}
    />
  ),
  Scholar: (props) => (
    <Icon
      d={[
        "M22 10v6M2 10l10-5 10 5-10 5z",
        "M6 12v5c3 3 9 3 12 0v-5",
      ]}
      {...props}
    />
  ),
  BookOpen: (props) => (
    <Icon
      d={[
        "M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z",
        "M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z",
      ]}
      {...props}
    />
  ),
  Award: (props) => (
    <Icon
      d={[
        "M12 15a7 7 0 1 0 0-14 7 7 0 0 0 0 14z",
        "M8.21 13.89L7 23l5-3 5 3-1.21-9.12",
      ]}
      {...props}
    />
  ),
};
