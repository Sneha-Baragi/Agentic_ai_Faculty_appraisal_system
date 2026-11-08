import React, { useMemo } from "react";
import { Icons } from "./ui/Icons.jsx";

export function EvidenceVaultSection({ evidence = [], activities = [] }) {
  const activityMap = useMemo(() => {
    const map = {};
    for (const a of activities) {
      map[a.id] = a;
    }
    return map;
  }, [activities]);

  return (
    <section className="bg-white rounded-lg border border-[#DCE5E1] p-5 sm:p-6 shadow-xs space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-[#DCE5E1] pb-4">
        <div>
          <span className="text-[11px] font-semibold uppercase tracking-wider text-[#73817C]">
            Evidence Repository
          </span>
          <h2 className="text-xl font-bold text-[#192522] mt-0.5">Uploaded Evidence Files</h2>
          <p className="text-xs text-[#53635E] mt-1">
            Documentation, certificates, and publications attached to your appraisal activities.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#194537]/10 text-[#194537] text-xs font-semibold">
            <Icons.Evidence className="w-3.5 h-3.5" />
            {evidence.length} {evidence.length === 1 ? "File" : "Files"}
          </span>
        </div>
      </div>

      {evidence.length === 0 ? (
        <div className="py-12 text-center rounded-lg border border-dashed border-[#DCE5E1] bg-[#F8FAF9]">
          <Icons.Evidence className="w-10 h-10 text-[#73817C] mx-auto mb-2 opacity-50" />
          <h3 className="text-sm font-semibold text-[#192522]">No evidence files uploaded</h3>
          <p className="text-xs text-[#53635E] mt-1 max-w-md mx-auto">
            Evidence documents are uploaded directly against activities in your Research, Teaching, or Service sections.
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-[#53635E]">
            <thead className="bg-[#F8FAF9] text-xs font-semibold text-[#73817C] border-b border-[#DCE5E1]">
              <tr>
                <th className="py-3 px-4">Document Name</th>
                <th className="py-3 px-4">Associated Activity</th>
                <th className="py-3 px-4">Category</th>
                <th className="py-3 px-4">Size</th>
                <th className="py-3 px-4">Uploaded Date</th>
                <th className="py-3 px-4 text-center">Validation</th>
                <th className="py-3 px-4 text-center">Extraction</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#DCE5E1]">
              {evidence.map((file) => {
                const act = activityMap[file.activity_id];
                const vTone =
                  file.validation_status === "valid"
                    ? "bg-emerald-100 text-emerald-800"
                    : file.validation_status === "invalid"
                    ? "bg-red-100 text-red-800"
                    : "bg-amber-100 text-amber-800";

                const eTone =
                  file.extraction_status === "extracted"
                    ? "bg-emerald-100 text-emerald-800"
                    : file.extraction_status === "failed"
                    ? "bg-red-100 text-red-800"
                    : "bg-amber-100 text-amber-800";

                return (
                  <tr key={file.id} className="hover:bg-[#F8FAF9] transition-colors">
                    <td className="py-3 px-4 font-semibold text-[#192522] min-w-[200px]">
                      <div className="flex items-center gap-2">
                        <Icons.Evidence className="w-4 h-4 text-[#194537] shrink-0" />
                        <span className="truncate">{file.original_filename || "evidence_doc"}</span>
                      </div>
                    </td>
                    <td className="py-3 px-4 max-w-xs truncate">
                      {act ? act.title : <span className="italic text-[#73817C]">Unlinked</span>}
                    </td>
                    <td className="py-3 px-4 capitalize">
                      {act?.category ? (
                        <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 text-xs font-medium">
                          {act.category}
                        </span>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="py-3 px-4 text-xs font-mono">
                      {file.file_size ? `${(file.file_size / 1024).toFixed(1)} KB` : "—"}
                    </td>
                    <td className="py-3 px-4 text-xs">
                      {file.upload_timestamp
                        ? new Date(file.upload_timestamp).toLocaleDateString()
                        : "—"}
                    </td>
                    <td className="py-3 px-4 text-center">
                      <span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-semibold ${vTone}`}>
                        {file.validation_status || "pending"}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-center">
                      <span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-semibold ${eTone}`}>
                        {file.extraction_status || "pending"}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
