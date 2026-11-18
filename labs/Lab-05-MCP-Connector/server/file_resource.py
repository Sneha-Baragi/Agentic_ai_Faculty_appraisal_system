"""Safe File Resource with Directory Boundary Enforcement.

Course: Agentic AI (26ECAC401)
Lab: 5 - MCP-Style Connector
Scenario: Local File Resource with Safe Directory Boundary

Provides safe file read and file listing operations strictly restricted to
the declared `safe_data/` directory boundary. Prevents directory traversal attacks
(e.g., `../../backend/.env`, `../README.md`) and unauthorized absolute path access
(e.g., `C:\\Windows\\win.ini`, `/some/unauthorized/file.txt`).
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


class FileResource:
    """Resource handling access to local files within a strict safe boundary."""

    def __init__(self, safe_dir: Optional[Union[str, Path]] = None) -> None:
        if safe_dir is None:
            lab_root = Path(__file__).resolve().parent.parent
            self.safe_dir = (lab_root / "safe_data").resolve()
        else:
            self.safe_dir = Path(safe_dir).resolve()

        self.safe_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_and_validate_path(self, requested_path: Union[str, Path]) -> Union[Path, Dict[str, Any]]:
        """Resolve requested path and ensure it remains strictly inside safe_dir.

        Returns:
            Resolved Path object if valid and within boundary,
            or structured error dict if permission denied.
        """
        raw_path = Path(requested_path)

        # 1. Resolve path to canonical absolute representation (resolving symlinks and ../)
        try:
            if raw_path.is_absolute():
                resolved_target = raw_path.resolve()
            else:
                resolved_target = (self.safe_dir / raw_path).resolve()
        except Exception:
            return {
                "status": "error",
                "error_code": "INVALID_PATH",
                "message": "Access denied: unable to resolve the requested path.",
            }

        # 2. Strict Boundary Containment Check
        # Does resolved_target reside within self.safe_dir?
        try:
            resolved_target.relative_to(self.safe_dir)
        except ValueError:
            # Traversal attempt or external path detected
            # Note: We do NOT echo the full absolute target to prevent path disclosure
            return {
                "status": "error",
                "error_code": "PERMISSION_DENIED",
                "message": (
                    "Security violation: Access denied. The requested path traverses "
                    "outside the designated safe data directory boundary."
                ),
            }

        return resolved_target

    def read_file(self, file_path: str) -> Dict[str, Any]:
        """Read content of a file located within the safe data directory.

        Args:
            file_path: Relative or absolute file path to read.

        Returns:
            Structured dict containing status, file_name, content, and size,
            or a structured error dict if unauthorized or missing.
        """
        # Validate path containment BEFORE reading
        result = self._resolve_and_validate_path(file_path)
        if isinstance(result, dict):
            # Error returned from validation
            return result

        resolved_target: Path = result

        # Check existence and type
        if not resolved_target.exists() or not resolved_target.is_file():
            return {
                "status": "error",
                "error_code": "FILE_NOT_FOUND",
                "message": (
                    f"The requested file was not found inside the safe data directory: "
                    f"'{resolved_target.name}'"
                ),
            }

        # Safe read
        try:
            with open(resolved_target, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            rel_path = resolved_target.relative_to(self.safe_dir)
            return {
                "status": "success",
                "file_name": resolved_target.name,
                "relative_path": str(rel_path).replace("\\", "/"),
                "size_bytes": len(content.encode("utf-8")),
                "content": content,
            }
        except Exception as exc:
            return {
                "status": "error",
                "error_code": "READ_ERROR",
                "message": f"Failed to read file content: {str(exc)}",
            }

    def list_files(self, subdir: str = "") -> Dict[str, Any]:
        """List files available inside the safe data directory.

        Args:
            subdir: Optional relative subdirectory within safe_data.

        Returns:
            Structured dict containing status, file count, and list of file metadata.
        """
        result = self._resolve_and_validate_path(subdir)
        if isinstance(result, dict):
            return result

        target_dir: Path = result

        if not target_dir.exists() or not target_dir.is_dir():
            return {
                "status": "error",
                "error_code": "DIRECTORY_NOT_FOUND",
                "message": "The requested directory was not found inside the safe data directory.",
            }

        try:
            files_list: List[Dict[str, Any]] = []
            for item in sorted(target_dir.iterdir()):
                if item.is_file():
                    rel = item.relative_to(self.safe_dir)
                    files_list.append({
                        "name": item.name,
                        "relative_path": str(rel).replace("\\", "/"),
                        "size_bytes": item.stat().st_size,
                        "extension": item.suffix,
                    })

            rel_dir = str(target_dir.relative_to(self.safe_dir)).replace("\\", "/") or "."
            return {
                "status": "success",
                "directory": rel_dir,
                "file_count": len(files_list),
                "files": files_list,
            }
        except Exception as exc:
            return {
                "status": "error",
                "error_code": "LIST_ERROR",
                "message": f"Failed to list directory contents: {str(exc)}",
            }
