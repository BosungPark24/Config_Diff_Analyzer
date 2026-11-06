"""WAS baseline configuration analyzer (Python 3.10+, standard library only)."""
from __future__ import annotations

import csv
import difflib
import json
import os
import shutil
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
import xml.etree.ElementTree as ET
from pathlib import Path

SERVER_TYPES = ("WebLogic", "JBoss", "Tomcat", "Apache", "OHS", "Nginx")
APP_VERSION = "v0.2"
APP_TITLE = f"ConfigAnalyzer {APP_VERSION}"


def get_app_root() -> Path:
    """Return the directory beside the executable, or beside this source file."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def normalize(value: str | None) -> str:
    return " ".join((value or "").split())


def read_text_file(path: Path) -> str:
    """Read common WAS text files, preferring UTF-8 and then Korean encodings."""
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            pass
    return data.decode("utf-8", errors="replace")


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def xml_values(root: ET.Element) -> dict[str, str]:
    """Flatten XML to stable XPath-like node, attribute, and text keys."""
    values: dict[str, str] = {}

    def walk(element: ET.Element, path: str) -> None:
        values[path] = "<element>"
        for key, value in sorted(element.attrib.items()):
            values[f"{path}/@{local_name(key)}"] = normalize(value)
        text = normalize(element.text)
        if text:
            values[f"{path}/text()"] = text
        counts: dict[str, int] = {}
        for child in list(element):
            name = local_name(child.tag)
            counts[name] = counts.get(name, 0) + 1
            child_path = f"{path}/{name}[{counts[name]}]"
            walk(child, child_path)

    root_name = local_name(root.tag)
    walk(root, f"/{root_name}[1]")
    return values


def parse_properties(text: str) -> dict[str, str]:
    """Parse Java-style properties and simple KEY=VALUE/KEY:VALUE config files."""
    result: dict[str, str] = {}
    logical_lines: list[str] = []
    pending = ""
    for line in text.splitlines():
        current = line.rstrip()
        if pending:
            current = pending + current.lstrip()
        if current.endswith("\\") and not current.endswith("\\\\"):
            pending = current[:-1]
            continue
        logical_lines.append(pending + current if pending else current)
        pending = ""
    if pending:
        logical_lines.append(pending)

    for line in logical_lines:
        stripped = line.lstrip()
        if not stripped or stripped.startswith(("#", "!")):
            continue
        # Find first unescaped separator or whitespace (Java properties syntax).
        sep = None
        escaped = False
        for i, char in enumerate(line):
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char in "=:" or char.isspace():
                sep = i
                break
        if sep is None:
            key, value = line.strip(), ""
        else:
            key = line[:sep].strip()
            remainder = line[sep:]
            remainder = remainder.lstrip()
            if remainder.startswith(("=", ":")):
                remainder = remainder[1:]
            value = remainder.strip()
        if key:
            result[key] = value
    return result


def compare_values(baseline: dict[str, str], target: dict[str, str]) -> list[dict[str, str]]:
    rows = []
    for key in sorted(set(baseline) | set(target)):
        if key not in baseline:
            kind, old, new = "Added", "", target[key]
        elif key not in target:
            kind, old, new = "Removed", baseline[key], ""
        elif baseline[key] != target[key]:
            kind, old, new = "Modified", baseline[key], target[key]
        else:
            continue
        rows.append({"type": kind, "path": key, "baseline": old, "target": new})
    return rows


class WasConfigAnalyzer:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1180x700")
        self.root.minsize(850, 500)
        self.app_root = get_app_root()
        self.baselines_dir = self.app_root / "baselines"
        self.metadata_path = self.baselines_dir / "metadata.json"
        self.metadata: dict = {"versions": {name: {} for name in SERVER_TYPES}}
        self.selected_baseline: Path | None = None
        self.target_path: Path | None = None
        self.result_rows: list[dict[str, str]] = []
        self.root.report_callback_exception = self._report_callback_exception
        self._load_metadata()
        self._build_ui()
        self._populate_tree()

    def _report_callback_exception(self, exc_type, exc_value, _traceback) -> None:
        messagebox.showerror(
            "화면 처리 오류",
            f"화면을 표시하는 중 오류가 발생했습니다.\n\n{exc_type.__name__}: {exc_value}",
            parent=self.root,
        )

    def _load_metadata(self) -> None:
        if not self.metadata_path.exists():
            return
        try:
            loaded = json.loads(self.metadata_path.read_text(encoding="utf-8"))
            versions = loaded.get("versions", {})
            self.metadata = {"versions": {name: versions.get(name, {}) for name in SERVER_TYPES}}
        except (OSError, json.JSONDecodeError) as exc:
            messagebox.showwarning("Metadata", f"메타데이터를 읽지 못했습니다. 새 메타데이터를 사용합니다.\n{exc}")

    def _save_metadata(self) -> None:
        self.baselines_dir.mkdir(parents=True, exist_ok=True)
        temp = self.metadata_path.with_suffix(".json.tmp")
        temp.write_text(json.dumps(self.metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.metadata_path)

    def _build_ui(self) -> None:
        style = ttk.Style(self.root)
        for theme in ("winnative", "clam"):
            if theme in style.theme_names():
                style.theme_use(theme)
                break
        style.configure("Treeview", rowheight=20, borderwidth=1, relief="solid")
        style.configure("Treeview.Heading", relief="raised")
        outer = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        outer.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        left = ttk.Frame(outer, padding=4)
        right = ttk.Frame(outer, padding=4)
        outer.add(left, weight=1)
        outer.add(right, weight=3)

        ttk.Label(left, text="Server Baseline Manager").pack(anchor="w", pady=(0, 4))
        self.tree = ttk.Treeview(left, show="tree", selectmode="browse")
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        buttons = ttk.Frame(left)
        buttons.pack(fill=tk.X, pady=(5, 0))
        for label, command in (("버전 추가", self.add_version), ("버전 삭제", self.delete_version),
                               ("Pure 파일 등록", self.add_pure_file), ("Pure 파일 삭제", self.delete_pure_file)):
            ttk.Button(buttons, text=label, command=command).pack(fill=tk.X, pady=1)

        ttk.Label(right, text="Comparison & Inspection").pack(anchor="w", pady=(0, 4))
        info = ttk.LabelFrame(right, text="Selected Pure / Target", padding=5)
        info.pack(fill=tk.X)
        self.pure_label = ttk.Label(info, text="Pure: 선택되지 않음", anchor="w")
        self.pure_label.grid(row=0, column=0, columnspan=3, sticky="ew", pady=2)
        self.target_var = tk.StringVar()
        ttk.Label(info, text="Target:").grid(row=1, column=0, sticky="w")
        ttk.Entry(info, textvariable=self.target_var, state="readonly").grid(row=1, column=1, sticky="ew", padx=4)
        ttk.Button(info, text="찾아보기...", command=self.choose_target).grid(row=1, column=2, padx=2)
        ttk.Button(info, text="Compare 실행", command=self.compare).grid(row=0, column=3, rowspan=2, padx=(8, 2))
        info.columnconfigure(1, weight=1)

        self.result_summary = ttk.Label(
            right,
            text="Pure 설정 파일과 비교 자료를 선택한 뒤 Compare를 실행하면 전체 파일을 나란히 표시합니다.\n"
                 "변경된 줄은 색상으로 구분하고, 공백·들여쓰기·주석을 포함한 원문 전체를 확인할 수 있습니다.",
            justify=tk.LEFT,
            anchor="nw",
        )
        self.result_summary.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        bottom = ttk.Frame(self.root, relief=tk.SUNKEN, padding=(5, 2))
        bottom.pack(fill=tk.X, side=tk.BOTTOM)
        self.status = ttk.Label(bottom, text="Ready", anchor="w")
        self.status.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(bottom, text="Export to CSV...", command=self.export_csv).pack(side=tk.RIGHT)

    def _populate_tree(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for was in SERVER_TYPES:
            was_id = self.tree.insert("", "end", iid=f"was:{was}", text=was, open=True)
            for version, files in sorted(self.metadata["versions"].get(was, {}).items()):
                version_id = f"version:{was}:{version}"
                self.tree.insert(was_id, "end", iid=version_id, text=version, open=True)
                for file_name, relpath in sorted(files.items()):
                    self.tree.insert(version_id, "end", text=file_name, values=(relpath,))

    def _on_tree_select(self, _event=None) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        item = self.tree.item(selection[0])
        relpath = item.get("values", [])
        if not relpath:
            return
        candidate = (self.baselines_dir / relpath[0]).resolve()
        try:
            candidate.relative_to(self.baselines_dir.resolve())
        except ValueError:
            return
        self.selected_baseline = candidate
        self.pure_label.configure(text=f"Pure: {candidate}")
        self.status.configure(text="Pure baseline selected")

    def add_version(self) -> None:
        was = self._selected_was()
        if not was:
            messagebox.showinfo("버전 추가", "좌측 트리에서 WAS 종류를 먼저 선택하세요.")
            return
        version = simpledialog.askstring("버전 추가", f"{was} 버전명을 입력하세요:", parent=self.root)
        if version is None:
            return
        version = version.strip()
        if not version or version in (".", "..") or any(c in version for c in '<>:"/\\|?*'):
            messagebox.showerror("버전 추가", "유효한 버전명을 입력하세요. 경로 구분 문자는 사용할 수 없습니다.")
            return
        versions = self.metadata["versions"].setdefault(was, {})
        if version in versions:
            messagebox.showerror("버전 추가", "이미 등록된 버전입니다.")
            return
        versions[version] = {}
        (self.baselines_dir / was / version).mkdir(parents=True, exist_ok=True)
        self._save_metadata()
        self._populate_tree()

    def delete_version(self) -> None:
        selection = self.tree.selection()
        if not selection or not selection[0].startswith("version:"):
            messagebox.showinfo("버전 삭제", "삭제할 버전을 선택하세요.")
            return
        _, was, version = selection[0].split(":", 2)
        if not messagebox.askyesno("버전 삭제", f"'{was} / {version}' 버전과 내부 Pure 파일을 삭제할까요?"):
            return
        folder = (self.baselines_dir / was / version).resolve()
        try:
            folder.relative_to(self.baselines_dir.resolve())
            if folder.exists():
                shutil.rmtree(folder)
        except (ValueError, OSError) as exc:
            messagebox.showerror("버전 삭제", str(exc))
            return
        self.metadata["versions"][was].pop(version, None)
        self._save_metadata()
        self.selected_baseline = None
        self.pure_label.configure(text="Pure: 선택되지 않음")
        self._populate_tree()

    def add_pure_file(self) -> None:
        selection = self.tree.selection()
        if not selection or not selection[0].startswith("version:"):
            messagebox.showinfo("Pure 파일 등록", "Pure 파일을 등록할 버전을 선택하세요.")
            return
        _, was, version = selection[0].split(":", 2)
        source = filedialog.askopenfilename(title="순정 설정 파일 선택")
        if not source:
            return
        src = Path(source)
        destination_dir = self.baselines_dir / was / version
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / src.name
        if destination.exists() and not messagebox.askyesno("파일 덮어쓰기", f"{src.name}이(가) 이미 있습니다. 덮어쓸까요?"):
            return
        try:
            shutil.copy2(src, destination)
        except OSError as exc:
            messagebox.showerror("파일 복사 오류", str(exc))
            return
        relpath = destination.relative_to(self.baselines_dir).as_posix()
        self.metadata["versions"][was][version][src.name] = relpath
        self._save_metadata()
        self._populate_tree()

    def delete_pure_file(self) -> None:
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Pure 파일 삭제", "삭제할 Pure 파일을 선택하세요.")
            return
        item = self.tree.item(selection[0])
        rels = item.get("values", [])
        if not rels:
            messagebox.showinfo("Pure 파일 삭제", "트리에서 Pure 파일을 선택하세요.")
            return
        parent_parts = self.tree.item(self.tree.parent(selection[0]), "text")
        was = self.tree.item(self.tree.parent(self.tree.parent(selection[0])), "text")
        name = item["text"]
        if not messagebox.askyesno("Pure 파일 삭제", f"'{name}' 파일을 baseline 저장소에서 삭제할까요?"):
            return
        path = (self.baselines_dir / rels[0]).resolve()
        try:
            path.relative_to(self.baselines_dir.resolve())
            path.unlink(missing_ok=True)
        except (ValueError, OSError) as exc:
            messagebox.showerror("Pure 파일 삭제", str(exc))
            return
        self.metadata["versions"].get(was, {}).get(parent_parts, {}).pop(name, None)
        self._save_metadata()
        if self.selected_baseline == path:
            self.selected_baseline = None
            self.pure_label.configure(text="Pure: 선택되지 않음")
        self._populate_tree()

    def _selected_was(self) -> str | None:
        selection = self.tree.selection()
        if not selection:
            return None
        item = selection[0]
        if item.startswith("was:"):
            return item.split(":", 1)[1]
        if item.startswith("version:"):
            return item.split(":", 2)[1]
        parent = self.tree.parent(item)
        return self.tree.item(self.tree.parent(parent), "text") if parent else None

    def choose_target(self) -> None:
        filename = filedialog.askopenfilename(title="분석 대상 설정 파일 선택")
        if filename:
            self.target_path = Path(filename)
            self.target_var.set(str(self.target_path))

    def compare(self) -> None:
        if not self.selected_baseline or not self.selected_baseline.is_file():
            messagebox.showerror("Compare", "좌측 트리에서 존재하는 Pure 파일을 선택하세요.")
            return
        if not self.target_path or not self.target_path.is_file():
            messagebox.showerror("Compare", "분석 대상(Target) 파일을 선택하세요.")
            return
        try:
            base_text = read_text_file(self.selected_baseline)
            target_text = read_text_file(self.target_path)
            if self.selected_baseline.suffix.lower() == ".xml":
                try:
                    base_root = ET.fromstring(base_text)
                except ET.ParseError as exc:
                    raise ValueError(f"Pure XML 문법 오류: {exc}") from exc
                try:
                    target_root = ET.fromstring(target_text)
                except ET.ParseError as exc:
                    raise ValueError(f"Target XML 문법 오류: {exc}") from exc
                rows = compare_values(xml_values(base_root), xml_values(target_root))
            else:
                rows = compare_values(parse_properties(read_text_file(self.selected_baseline)),
                                      parse_properties(read_text_file(self.target_path)))
        except (OSError, ValueError) as exc:
            messagebox.showerror("비교 오류", str(exc))
            return
        self.result_rows = rows
        counts = {kind: sum(r["type"] == kind for r in rows) for kind in ("Added", "Modified", "Removed")}
        self.status.configure(text=f"비교 완료: 총 {len(rows)}건 (Added {counts['Added']} / Modified {counts['Modified']} / Removed {counts['Removed']})")
        self.result_summary.configure(
            text=(f"Pure config: {self.selected_baseline}\n"
                  f"비교 자료: {self.target_path}\n\n"
                  f"의미 기반 변경 요약: 총 {len(rows)}건  "
                  f"(Added {counts['Added']} / Modified {counts['Modified']} / Removed {counts['Removed']})\n\n"
                  "전체 파일 비교 창을 열었습니다. 초록색은 추가, 빨간색은 삭제, 노란색은 변경된 줄입니다.")
        )
        self._show_full_file_diff(base_text, target_text)

    def _show_full_file_diff(self, pure_text: str, target_text: str) -> None:
        """Show both complete files in aligned, read-only panes with diff coloring."""
        pure_lines = pure_text.splitlines()
        target_lines = target_text.splitlines()
        use_word_wrap = (
            self.selected_baseline.suffix.lower() == ".conf"
            or self.target_path.suffix.lower() == ".conf"
        )
        matcher = difflib.SequenceMatcher(a=pure_lines, b=target_lines, autojunk=False)
        aligned: list[tuple[int | None, str, int | None, str, str]] = []
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                for offset in range(i2 - i1):
                    aligned.append((i1 + offset + 1, pure_lines[i1 + offset],
                                    j1 + offset + 1, target_lines[j1 + offset], "equal"))
            elif tag == "replace":
                size = max(i2 - i1, j2 - j1)
                for offset in range(size):
                    old_index = i1 + offset if i1 + offset < i2 else None
                    new_index = j1 + offset if j1 + offset < j2 else None
                    kind = "modified" if old_index is not None and new_index is not None else ("removed" if old_index is not None else "added")
                    aligned.append((old_index + 1 if old_index is not None else None,
                                    pure_lines[old_index] if old_index is not None else "",
                                    new_index + 1 if new_index is not None else None,
                                    target_lines[new_index] if new_index is not None else "", kind))
            elif tag == "delete":
                for index in range(i1, i2):
                    aligned.append((index + 1, pure_lines[index], None, "", "removed"))
            elif tag == "insert":
                for index in range(j1, j2):
                    aligned.append((None, "", index + 1, target_lines[index], "added"))

        win = tk.Toplevel(self.root)
        win.title(f"File Compare - {self.selected_baseline.name}  |  {self.target_path.name}")
        win.geometry("1400x850")
        win.minsize(800, 500)
        loading = ttk.Label(win, text="비교 화면을 구성하는 중...", anchor="w", padding=(6, 4))
        loading.pack(fill=tk.X)
        wrap_var = tk.BooleanVar(value=use_word_wrap)
        toolbar = ttk.Frame(win, padding=(5, 2))
        toolbar.pack(fill=tk.X)
        ttk.Checkbutton(
            toolbar,
            text="자동 줄 바꿈",
            variable=wrap_var,
        ).pack(side=tk.LEFT)
        diff_area = ttk.Frame(win)
        diff_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
        diff_area.rowconfigure(0, weight=1)
        diff_area.columnconfigure(0, weight=1, uniform="compare_panes")
        diff_area.columnconfigure(1, weight=1, uniform="compare_panes")
        diff_area.columnconfigure(2, weight=0)
        pane_widgets: list[tk.Text] = []
        xbar_widgets: list[ttk.Scrollbar] = []
        for column, (role, file_path, role_color) in enumerate((
            ("PURE BASELINE", self.selected_baseline, "#204a87"),
            ("TARGET COMPARISON", self.target_path, "#7a3e00"),
        )):
            frame = ttk.Frame(diff_area)
            frame.grid(row=0, column=column, sticky="nsew")
            header = ttk.Frame(frame, padding=(6, 5))
            header.configure(height=96)
            header.grid_propagate(False)
            header.grid(row=0, column=0, sticky="ew")
            frame.rowconfigure(0, minsize=96, weight=0)
            ttk.Label(
                header,
                text=role,
                foreground=role_color,
                font=("TkDefaultFont", 9, "bold"),
            ).pack(anchor="w")
            ttk.Label(
                header,
                text=file_path.name,
                font=("TkDefaultFont", 11, "bold"),
            ).pack(anchor="w", pady=(1, 0))
            ttk.Label(
                header,
                text=str(file_path),
                font=("TkFixedFont", 8),
                wraplength=600,
                justify=tk.LEFT,
            ).pack(anchor="w", fill=tk.X, pady=(2, 0))

            text = tk.Text(
                frame,
                wrap="word" if use_word_wrap else "none",
                font="TkFixedFont",
                undo=False,
                padx=4,
                pady=3,
                foreground="#161616",
                selectforeground="#161616",
                selectbackground="#b9d5f0",
            )
            text.tag_configure("added", background="#dff0d8", foreground="#161616")
            text.tag_configure("removed", background="#f2dede", foreground="#161616")
            text.tag_configure("modified", background="#fcf8e3", foreground="#161616")
            text.tag_configure("drag_selection", background="#1558a6", foreground="#ffffff")
            text.tag_raise("drag_selection")
            xbar = ttk.Scrollbar(frame, orient=tk.HORIZONTAL, command=text.xview)
            text.configure(xscrollcommand=xbar.set)
            text.grid(row=1, column=0, sticky="nsew")
            xbar.grid(row=2, column=0, sticky="ew")
            if use_word_wrap:
                xbar.grid_remove()
            frame.rowconfigure(1, weight=1)
            frame.columnconfigure(0, weight=1)
            pane_widgets.append(text)
            xbar_widgets.append(xbar)

        def toggle_word_wrap(*_args) -> None:
            enabled = wrap_var.get()
            for widget, xbar in zip(pane_widgets, xbar_widgets):
                widget.configure(wrap="word" if enabled else "none")
                if enabled:
                    xbar.grid_remove()
                else:
                    xbar.grid()

        wrap_var.trace_add("write", toggle_word_wrap)

        shared_ybar = ttk.Scrollbar(diff_area, orient=tk.VERTICAL)
        shared_ybar.grid(row=0, column=2, sticky="ns")

        def scroll_both(*args) -> None:
            for widget in pane_widgets:
                widget.yview(*args)

        def update_shared_scroll(first: str, last: str) -> None:
            shared_ybar.set(first, last)

        shared_ybar.configure(command=scroll_both)

        def wheel_scroll(event):
            if event.delta:
                units = -1 * int(event.delta / 120)
                if units == 0:
                    units = -1 if event.delta > 0 else 1
                scroll_both("scroll", units, "units")
            elif getattr(event, "num", None) == 4:
                scroll_both("scroll", -3, "units")
            elif getattr(event, "num", None) == 5:
                scroll_both("scroll", 3, "units")
            return "break"

        for widget in pane_widgets:
            widget.configure(yscrollcommand=update_shared_scroll)
            widget.bind("<MouseWheel>", wheel_scroll)
            widget.bind("<Button-4>", wheel_scroll)
            widget.bind("<Button-5>", wheel_scroll)

            def begin_drag(event, current_widget=widget):
                current_widget.mark_set("drag_anchor", f"@{event.x},{event.y}")
                current_widget.tag_remove("drag_selection", "1.0", "end")

            def update_drag(event, current_widget=widget):
                anchor = current_widget.index("drag_anchor")
                current = current_widget.index(f"@{event.x},{event.y}")
                current_widget.tag_remove("drag_selection", "1.0", "end")
                if current_widget.compare(anchor, "<=", current):
                    start = anchor
                    end = current_widget.index(f"{current} +1c")
                else:
                    start = current
                    end = current_widget.index(f"{anchor} +1c")
                if current_widget.compare(start, "<", end):
                    current_widget.tag_add("drag_selection", start, end)

            widget.bind("<Button-1>", begin_drag, add="+")
            widget.bind("<B1-Motion>", update_drag, add="+")

        ttk.Label(win, text="초록색: 추가   빨간색: 삭제   노란색: 변경", anchor="w", relief=tk.SUNKEN, padding=3).pack(fill=tk.X, side=tk.BOTTOM)

        def populate_diff() -> None:
            try:
                loading.configure(text="비교 내용을 표시하는 중...")
                left_content: list[str] = []
                right_content: list[str] = []
                tag_rows: list[dict[str, list[int]]] = [
                    {"added": [], "removed": [], "modified": []},
                    {"added": [], "removed": [], "modified": []},
                ]
                for row_index, (old_no, old_line, new_no, new_line, kind) in enumerate(aligned, start=1):
                    left_content.append(f"{old_no or '':>6}  {old_line}\n")
                    right_content.append(f"{new_no or '':>6}  {new_line}\n")
                    if kind in ("removed", "modified"):
                        tag_rows[0][kind].append(row_index)
                    if kind in ("added", "modified"):
                        tag_rows[1][kind].append(row_index)

                for widget, content, tags in zip(
                    pane_widgets,
                    ("".join(left_content), "".join(right_content)),
                    tag_rows,
                ):
                    widget.insert("1.0", content)
                    for tag, rows in tags.items():
                        if not rows:
                            continue
                        # Apply each contiguous changed block in one Tk call.
                        ranges: list[str] = []
                        start = previous = rows[0]
                        for current in rows[1:]:
                            if current != previous + 1:
                                ranges.extend((f"{start}.0", f"{previous + 1}.0"))
                                start = current
                            previous = current
                        ranges.extend((f"{start}.0", f"{previous + 1}.0"))
                        widget.tag_add(tag, *ranges)
                    widget.configure(state="disabled")
                loading.destroy()
            except Exception as exc:
                loading.configure(text=f"비교 표시 오류: {exc}")
                messagebox.showerror("비교 화면 오류", f"비교 내용을 표시하지 못했습니다.\n{exc}", parent=win)

        # Let Tk draw the two panes first; large files are then inserted in a single batch.
        win.after(50, populate_diff)

    def export_csv(self) -> None:
        if not self.result_rows:
            messagebox.showinfo("CSV 내보내기", "비교 결과가 없거나 아직 비교를 실행하지 않았습니다.")
            return
        path = filedialog.asksaveasfilename(title="결과 CSV 저장", defaultextension=".csv",
                                            filetypes=(("CSV files", "*.csv"), ("All files", "*.*")))
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.writer(handle)
                writer.writerow(("Type", "Config Path / XPath / Key", "Pure Baseline Value", "Target Value"))
                for row in self.result_rows:
                    writer.writerow((row["type"], row["path"], row["baseline"], row["target"]))
        except OSError as exc:
            messagebox.showerror("CSV 내보내기 오류", str(exc))
            return
        self.status.configure(text=f"CSV 저장 완료: {path}")


def main() -> None:
    root = tk.Tk()
    WasConfigAnalyzer(root)
    root.mainloop()


if __name__ == "__main__":
    main()
