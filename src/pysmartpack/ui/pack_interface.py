"""The main packaging workflow interface."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QSplitter,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CardWidget,
    FluentIcon,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    PrimaryPushButton,
    ProgressBar,
    PushButton,
    RadioButton,
    StrongBodyLabel,
    SubtitleLabel,
    SwitchButton,
    TextEdit,
    TitleLabel,
    TreeWidget,
)

from .. import __version__
from ..core import config_generator, persistence, size_analyzer
from ..core.models import (
    Advice,
    FileCategory,
    OutputMode,
    PackBackend,
    PackConfig,
    PackResult,
    ScanResult,
    Severity,
)
from .theme import Tokens, log_html
from .workers import AdviceWorker, PackWorker, ScanWorker

_CATEGORY_LABEL = {
    FileCategory.DATA_TABLE: "表格数据",
    FileCategory.DATA_MODEL: "模型/数组",
    FileCategory.DATA_CONFIG: "配置文件",
    FileCategory.DATA_DOC: "文档",
    FileCategory.DATA_MEDIA: "媒体/资源",
    FileCategory.DATA_DB: "数据库",
    FileCategory.BINARY: "原生扩展",
    FileCategory.OTHER: "其他",
}


def _card(title: str) -> tuple[CardWidget, QVBoxLayout]:
    card = CardWidget()
    layout = QVBoxLayout(card)
    layout.setContentsMargins(16, 14, 16, 14)
    layout.setSpacing(10)
    layout.addWidget(StrongBodyLabel(title))
    return card, layout


class PackInterface(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("packInterface")

        self._scan: Optional[ScanResult] = None
        self._scan_worker: Optional[ScanWorker] = None
        self._advice_worker: Optional[AdviceWorker] = None
        self._pack_worker: Optional[PackWorker] = None
        self._entry_items: Dict[QTreeWidgetItem, str] = {}
        self._data_items: Dict[QTreeWidgetItem, object] = {}
        self._last_output = ""

        self._build_ui()

    # --------------------------------------------------------------- UI build
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 18)
        root.setSpacing(14)

        header = QVBoxLayout()
        header.setSpacing(2)
        title = TitleLabel("PySmartPack")
        subtitle = CaptionLabel(f"智能 Python 打包器 · PyInstaller / Nuitka 的现代化前端 · v{__version__}")
        subtitle.setStyleSheet(f"color:{Tokens.INK_SUBTLE};")
        header.addWidget(title)
        header.addWidget(subtitle)
        root.addLayout(header)

        # --- project selection ---
        proj_card, proj_layout = _card("1 · 选择项目")
        row = QHBoxLayout()
        self.path_edit = LineEdit()
        self.path_edit.setPlaceholderText("选择一个 Python 项目目录或单个 .py 文件…")
        self.path_edit.setReadOnly(True)
        self.btn_browse = PushButton(FluentIcon.FOLDER_ADD, "浏览目录")
        self.btn_browse_file = PushButton(FluentIcon.DOCUMENT, "选择文件")
        self.btn_rescan = PushButton(FluentIcon.SYNC, "重新扫描")
        self.btn_rescan.setEnabled(False)
        row.addWidget(self.path_edit, 1)
        row.addWidget(self.btn_browse)
        row.addWidget(self.btn_browse_file)
        row.addWidget(self.btn_rescan)
        proj_layout.addLayout(row)
        root.addWidget(proj_card)

        # --- middle: tree + options ---
        splitter = QSplitter(Qt.Horizontal)

        tree_card, tree_layout = _card("2 · 扫描结果（可勾选，结果均可手动调整）")
        self.tree = TreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setMinimumHeight(240)
        tree_layout.addWidget(self.tree)
        splitter.addWidget(tree_card)

        opt_card, opt_layout = _card("3 · 打包选项")
        opt_layout.addWidget(CaptionLabel("打包策略"))
        self.rb_bundle = RadioButton("捆绑模式 · PyInstaller（快速，所有库一起打包）")
        self.rb_compile = RadioButton("编译模式 · Nuitka（先编译再打包，体积更小、启动更快）")
        self.rb_bundle.setChecked(True)
        self.strategy_group = QButtonGroup(self)
        self.strategy_group.addButton(self.rb_bundle)
        self.strategy_group.addButton(self.rb_compile)
        opt_layout.addWidget(self.rb_bundle)
        opt_layout.addWidget(self.rb_compile)

        opt_layout.addWidget(self._divider())
        opt_layout.addWidget(CaptionLabel("输出形式"))
        self.rb_onefile = RadioButton("单文件（onefile）")
        self.rb_onedir = RadioButton("单目录（onedir，推荐用于重型库）")
        self.rb_onefile.setChecked(True)
        self.output_group = QButtonGroup(self)
        self.output_group.addButton(self.rb_onefile)
        self.output_group.addButton(self.rb_onedir)
        opt_layout.addWidget(self.rb_onefile)
        opt_layout.addWidget(self.rb_onedir)

        opt_layout.addWidget(self._divider())
        name_row = QHBoxLayout()
        name_row.addWidget(BodyLabel("应用名称"))
        self.name_edit = LineEdit()
        self.name_edit.setPlaceholderText("app")
        name_row.addWidget(self.name_edit, 1)
        opt_layout.addLayout(name_row)

        console_row = QHBoxLayout()
        console_row.addWidget(BodyLabel("显示控制台窗口"))
        console_row.addStretch(1)
        self.sw_console = SwitchButton()
        self.sw_console.setChecked(True)
        console_row.addWidget(self.sw_console)
        opt_layout.addLayout(console_row)

        opt_layout.addWidget(self._divider())
        advise_row = QHBoxLayout()
        self.btn_advise = PushButton(FluentIcon.ROBOT, "智能分析建议")
        self.btn_preview = PushButton(FluentIcon.CODE, "预览命令 / spec")
        advise_row.addWidget(self.btn_advise)
        advise_row.addWidget(self.btn_preview)
        opt_layout.addLayout(advise_row)
        self.advice_view = TextEdit()
        self.advice_view.setReadOnly(True)
        self.advice_view.setPlaceholderText("打包策略建议会显示在这里（默认使用本地规则引擎；可在设置中开启 LLM）。")
        self.advice_view.setMaximumHeight(150)
        opt_layout.addWidget(self.advice_view)
        opt_layout.addStretch(1)
        splitter.addWidget(opt_card)
        splitter.setSizes([520, 420])
        root.addWidget(splitter, 1)

        # --- progress + log ---
        prog_row = QHBoxLayout()
        self.progress = ProgressBar()
        self.progress.setValue(0)
        self.status = CaptionLabel("就绪")
        self.status.setStyleSheet(f"color:{Tokens.INK_SUBTLE};")
        prog_row.addWidget(self.progress, 1)
        prog_row.addWidget(self.status)
        root.addLayout(prog_row)

        self.log = TextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(150)
        self.log.setStyleSheet(
            f"QTextEdit{{background:{Tokens.SURFACE_1};border:1px solid {Tokens.HAIRLINE};"
            f"border-radius:8px;}}")
        root.addWidget(self.log)

        # --- actions ---
        actions = QHBoxLayout()
        self.btn_pack = PrimaryPushButton(FluentIcon.PLAY_SOLID, "开始打包")
        self.btn_pack.setEnabled(False)
        self.btn_cancel = PushButton(FluentIcon.CANCEL, "取消")
        self.btn_cancel.setEnabled(False)
        self.btn_open = PushButton(FluentIcon.FOLDER, "打开输出目录")
        self.btn_open.setEnabled(False)
        actions.addStretch(1)
        actions.addWidget(self.btn_open)
        actions.addWidget(self.btn_cancel)
        actions.addWidget(self.btn_pack)
        root.addLayout(actions)

        self._connect()

    def _divider(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet(f"color:{Tokens.HAIRLINE};")
        return line

    def _connect(self) -> None:
        self.btn_browse.clicked.connect(self._choose_folder)
        self.btn_browse_file.clicked.connect(self._choose_file)
        self.btn_rescan.clicked.connect(self._start_scan)
        self.btn_advise.clicked.connect(self._run_advice)
        self.btn_preview.clicked.connect(self._preview_config)
        self.btn_pack.clicked.connect(self._start_pack)
        self.btn_cancel.clicked.connect(self._cancel_pack)
        self.btn_open.clicked.connect(self._open_output)
        self.rb_compile.toggled.connect(self._sync_default_name)

    # ----------------------------------------------------------- project pick
    def _choose_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择 Python 项目目录")
        if path:
            self.path_edit.setText(path)
            self._start_scan()

    def _choose_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择 Python 文件", filter="Python (*.py)")
        if path:
            self.path_edit.setText(path)
            self._start_scan()

    def _start_scan(self) -> None:
        path = self.path_edit.text().strip()
        if not path or not Path(path).exists():
            self._toast_error("路径无效", "请先选择一个存在的目录或文件。")
            return
        self._set_busy(True, "扫描中…")
        self.tree.clear()
        self._entry_items.clear()
        self._data_items.clear()
        self._scan_worker = ScanWorker(path)
        self._scan_worker.finished.connect(self._on_scan_done)
        self._scan_worker.failed.connect(self._on_scan_failed)
        self._scan_worker.start()
        persistence.add_recent_project(path)

    def _on_scan_failed(self, message: str) -> None:
        self._set_busy(False, "扫描失败")
        self._toast_error("扫描失败", message)

    def _on_scan_done(self, scan: ScanResult) -> None:
        self._scan = scan
        self._populate_tree(scan)
        self.btn_rescan.setEnabled(True)
        self.btn_pack.setEnabled(bool(scan.entry_points))
        best = scan.best_entry_point
        if best and not self.name_edit.text().strip():
            self.name_edit.setText(Path(best.path).stem)
        self._set_busy(False, "扫描完成")
        self._append_log(f"扫描完成：入口 {len(scan.entry_points)}、包 {len(scan.packages)}、"
                         f"数据文件 {len(scan.data_files)}、第三方依赖 {len(scan.third_party_imports)}。",
                         Severity.INFO)
        # auto rule-based advice (no network)
        self._run_advice()

    def _populate_tree(self, scan: ScanResult) -> None:
        self.tree.clear()
        self._entry_items.clear()
        self._data_items.clear()

        # entry points (radio-like: best one checked)
        ep_root = self._top("入口脚本", FluentIcon.PLAY)
        for i, ep in enumerate(scan.entry_points):
            item = QTreeWidgetItem([f"{Path(ep.path).name}  ·  {ep.reason} (score {ep.score})"])
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(0, Qt.Checked if i == 0 else Qt.Unchecked)
            ep_root.addChild(item)
            self._entry_items[item] = ep.path

        # packages
        if scan.packages:
            pkg_root = self._top("包结构", FluentIcon.LIBRARY)
            for pkg in scan.packages:
                pkg_root.addChild(QTreeWidgetItem([Path(pkg).name]))

        # data files grouped
        cats = scan.data_by_category()
        if cats:
            data_root = self._top("数据文件（取消勾选可排除）", FluentIcon.DOCUMENT)
            for cat_value, files in cats.items():
                label = _CATEGORY_LABEL.get(FileCategory(cat_value), cat_value)
                group = QTreeWidgetItem([f"{label} ({len(files)})"])
                data_root.addChild(group)
                for data in files:
                    leaf = QTreeWidgetItem([Path(data.path).name])
                    leaf.setFlags(leaf.flags() | Qt.ItemIsUserCheckable)
                    leaf.setCheckState(0, Qt.Checked if data.selected else Qt.Unchecked)
                    group.addChild(leaf)
                    self._data_items[leaf] = data
            data_root.setExpanded(True)

        # third-party deps
        if scan.third_party_imports:
            dep_root = self._top("第三方依赖", FluentIcon.EMBED)
            for name in scan.third_party_imports:
                dep_root.addChild(QTreeWidgetItem([name]))

        # dynamic imports / diagnostics
        if scan.dynamic_imports:
            dyn_root = self._top("动态导入（需关注）", FluentIcon.INFO)
            for d in scan.dynamic_imports:
                dyn_root.addChild(QTreeWidgetItem([f"{d.name}  @ {d.location}"]))

        # environment
        env_root = self._top("环境", FluentIcon.APPLICATION)
        env = scan.env
        env_root.addChild(QTreeWidgetItem([f"类型: {env.kind.value}"]))
        if env.python_version:
            env_root.addChild(QTreeWidgetItem([f"Python: {env.python_version}"]))
        if env.python_executable:
            env_root.addChild(QTreeWidgetItem([f"解释器: {env.python_executable}"]))
        env_root.addChild(QTreeWidgetItem([f"依赖来源: {env.source or '未解析'}"]))

        ep_root.setExpanded(True)

    def _top(self, text: str, icon: FluentIcon) -> QTreeWidgetItem:
        item = QTreeWidgetItem([text])
        self.tree.addTopLevelItem(item)
        item.setExpanded(True)
        return item

    # ----------------------------------------------------------------- advice
    def _run_advice(self) -> None:
        if not self._scan:
            return
        self.btn_advise.setEnabled(False)
        self.advice_view.setPlainText("分析中…")
        cfg = persistence.get_llm_config()
        self._advice_worker = AdviceWorker(self._scan, cfg)
        self._advice_worker.finished.connect(self._on_advice)
        self._advice_worker.start()

    def _on_advice(self, advice: Advice) -> None:
        self.btn_advise.setEnabled(True)
        lines = [
            f"来源: {advice.source}",
            f"推荐后端: {advice.recommended_backend.value} · 输出: {advice.recommended_output_mode.value}",
            "",
            f"数据策略: {advice.data_strategy}",
            f"理由: {advice.rationale}",
        ]
        if advice.suggested_hidden_imports:
            lines.append("建议 hidden-import: " + ", ".join(advice.suggested_hidden_imports))
        if advice.hidden_import_warnings:
            lines.append("")
            lines.append("提示:")
            lines += [f"  • {w}" for w in advice.hidden_import_warnings]
        self.advice_view.setPlainText("\n".join(lines))
        # set recommended output mode as a non-destructive default suggestion
        if advice.recommended_output_mode == OutputMode.ONEDIR and self.rb_onefile.isChecked():
            self.rb_onedir.setChecked(True)

    # ------------------------------------------------------------ config build
    def _build_config(self) -> Optional[PackConfig]:
        if not self._scan:
            return None
        entry = self._selected_entry()
        if not entry:
            self._toast_error("缺少入口", "请在扫描结果中勾选一个入口脚本。")
            return None
        # reflect data-file checkbox states back onto the scan model
        for item, data in self._data_items.items():
            data.selected = item.checkState(0) == Qt.Checked  # type: ignore[attr-defined]

        backend = PackBackend.NUITKA if self.rb_compile.isChecked() else PackBackend.PYINSTALLER
        mode = OutputMode.ONEFILE if self.rb_onefile.isChecked() else OutputMode.ONEDIR
        name = self.name_edit.text().strip() or Path(entry).stem
        return config_generator.build_pack_config(
            self._scan,
            entry_script=entry,
            backend=backend,
            output_mode=mode,
            app_name=name,
            console=self.sw_console.isChecked(),
            compile_first=self.rb_compile.isChecked(),
            bundle_all=self.rb_bundle.isChecked(),
        )

    def _selected_entry(self) -> str:
        for item, path in self._entry_items.items():
            if item.checkState(0) == Qt.Checked:
                return path
        return ""

    # ------------------------------------------------------------------ pack
    def _start_pack(self) -> None:
        cfg = self._build_config()
        if cfg is None:
            return
        self.log.clear()
        self.progress.setValue(0)
        self._set_packing(True)
        self._append_log(f"开始打包 [{cfg.backend.value} · {cfg.output_mode.value}] -> {cfg.app_name}",
                         Severity.INFO)
        self._pack_worker = PackWorker(cfg)
        self._pack_worker.log.connect(self._append_log)
        self._pack_worker.progress.connect(self.progress.setValue)
        self._pack_worker.finished.connect(self._on_pack_done)
        self._pack_worker.start()

    def _cancel_pack(self) -> None:
        if self._pack_worker:
            self._pack_worker.cancel()
            self.status.setText("正在取消…")

    def _on_pack_done(self, result: PackResult) -> None:
        self._set_packing(False)
        persistence.add_history({
            "name": Path(result.output_path).name if result.output_path else "",
            "backend": result.backend.value,
            "success": result.success,
            "duration_sec": round(result.duration_sec, 1),
            "output": result.output_path,
            "project": self._scan.root if self._scan else "",
        })
        if result.success:
            self._last_output = result.output_path
            self.btn_open.setEnabled(True)
            self.status.setText(f"完成 · {result.duration_sec:.1f}s")
            self._toast_success("打包成功", result.output_path)
            try:
                report = size_analyzer.analyze(result.output_path)
                self._append_log(f"产物体积: {report.total_human}", Severity.INFO)
                for e in report.entries[:8]:
                    self._append_log(f"  {e.human:>10}  {e.name}", Severity.INFO)
            except OSError:
                pass
        else:
            self.status.setText("失败")
            self._toast_error("打包失败", result.message)

    def _open_output(self) -> None:
        if not self._last_output:
            return
        target = Path(self._last_output)
        folder = target.parent if target.is_file() else target
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(folder))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(folder)])
            else:
                subprocess.Popen(["xdg-open", str(folder)])
        except OSError as exc:
            self._toast_error("无法打开目录", str(exc))

    # ---------------------------------------------------------------- preview
    def _preview_config(self) -> None:
        cfg = self._build_config()
        if cfg is None:
            return
        rendered = config_generator.render(cfg)
        text = "# 命令行参数\n" + " ".join(rendered["args"])
        if rendered["spec"]:
            text += "\n\n# PyInstaller .spec 预览\n" + rendered["spec"]
        self._show_text_dialog("打包配置预览", text)

    def _show_text_dialog(self, title: str, text: str) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.resize(720, 520)
        layout = QVBoxLayout(dlg)
        layout.addWidget(SubtitleLabel(title))
        view = TextEdit()
        view.setReadOnly(True)
        view.setPlainText(text)
        view.setStyleSheet(f"font-family:{Tokens.MONO_FONT},Consolas,monospace;")
        layout.addWidget(view)
        close = PushButton("关闭")
        close.clicked.connect(dlg.accept)
        layout.addWidget(close, alignment=Qt.AlignRight)
        dlg.exec()

    # ----------------------------------------------------------------- helpers
    def _append_log(self, line: str, severity: Severity) -> None:
        self.log.append(log_html(line, severity))

    def _sync_default_name(self) -> None:
        pass

    def _set_busy(self, busy: bool, status: str) -> None:
        self.status.setText(status)
        self.btn_browse.setEnabled(not busy)
        self.btn_browse_file.setEnabled(not busy)
        self.btn_rescan.setEnabled(not busy and self._scan is not None)

    def _set_packing(self, packing: bool) -> None:
        self.btn_pack.setEnabled(not packing)
        self.btn_cancel.setEnabled(packing)
        self.btn_browse.setEnabled(not packing)
        self.btn_browse_file.setEnabled(not packing)
        self.btn_rescan.setEnabled(not packing and self._scan is not None)
        self.btn_advise.setEnabled(not packing)
        self.status.setText("打包中…" if packing else self.status.text())

    def _toast_success(self, title: str, content: str) -> None:
        InfoBar.success(title, content, duration=4000,
                        position=InfoBarPosition.TOP_RIGHT, parent=self)

    def _toast_error(self, title: str, content: str) -> None:
        InfoBar.error(title, content, duration=6000,
                      position=InfoBarPosition.TOP_RIGHT, parent=self)
