import json

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .db import guilds, plants


ROLES = [
    "canopy",
    "understory",
    "groundcover",
    "nitrogen_fixer",
    "dynamic_accumulator",
    "pest_repellent",
    "pollinator",
    "windbreak",
    "other",
]


class AddMemberDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Guild Member")
        self.setMinimumWidth(350)

        layout = QFormLayout(self)

        self.plant_combo = QComboBox()
        all_plants = plants.get_all_plants()
        for p in all_plants:
            self.plant_combo.addItem(
                f"{p['common_name']} ({p['plant_type']})", p["id"]
            )
        layout.addRow("Plant:", self.plant_combo)

        self.role_combo = QComboBox()
        for r in ROLES:
            self.role_combo.addItem(r.replace("_", " ").title(), r)
        layout.addRow("Role:", self.role_combo)

        self.offset_x = QDoubleSpinBox()
        self.offset_x.setRange(-50, 50)
        self.offset_x.setSuffix(" m")
        self.offset_x.setDecimals(1)
        layout.addRow("Offset X:", self.offset_x)

        self.offset_y = QDoubleSpinBox()
        self.offset_y.setRange(-50, 50)
        self.offset_y.setSuffix(" m")
        self.offset_y.setDecimals(1)
        layout.addRow("Offset Y:", self.offset_y)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_data(self):
        return {
            "plant_id": self.plant_combo.currentData(),
            "role": self.role_combo.currentData(),
            "offset_x": self.offset_x.value(),
            "offset_y": self.offset_y.value(),
        }


class GuildPanel(QWidget):
    placeGuildRequested = pyqtSignal(dict)  # guild data with members

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._refresh_guild_list()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        label = QLabel("<b>Guild Library</b>")
        layout.addWidget(label)

        # Guild list
        self.guild_list = QListWidget()
        self.guild_list.currentItemChanged.connect(self._on_guild_selected)
        layout.addWidget(self.guild_list)

        # Buttons row 1
        btn_row1 = QHBoxLayout()
        self.new_btn = QPushButton("New Guild")
        self.new_btn.clicked.connect(self._on_new_guild)
        btn_row1.addWidget(self.new_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self._on_delete_guild)
        btn_row1.addWidget(self.delete_btn)

        self.dup_btn = QPushButton("Duplicate")
        self.dup_btn.setEnabled(False)
        self.dup_btn.clicked.connect(self._on_duplicate_guild)
        btn_row1.addWidget(self.dup_btn)
        layout.addLayout(btn_row1)

        # Detail area
        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setMaximumHeight(150)
        layout.addWidget(self.detail_text)

        # Members list
        members_label = QLabel("<b>Members</b>")
        layout.addWidget(members_label)

        self.members_list = QListWidget()
        self.members_list.setMaximumHeight(120)
        layout.addWidget(self.members_list)

        # Member buttons
        member_btns = QHBoxLayout()
        self.add_member_btn = QPushButton("Add Member")
        self.add_member_btn.setEnabled(False)
        self.add_member_btn.clicked.connect(self._on_add_member)
        member_btns.addWidget(self.add_member_btn)

        self.remove_member_btn = QPushButton("Remove")
        self.remove_member_btn.setEnabled(False)
        self.remove_member_btn.clicked.connect(self._on_remove_member)
        member_btns.addWidget(self.remove_member_btn)
        layout.addLayout(member_btns)

        # Action buttons
        btn_row2 = QHBoxLayout()
        self.place_btn = QPushButton("Place on Map")
        self.place_btn.setEnabled(False)
        self.place_btn.clicked.connect(self._on_place)
        btn_row2.addWidget(self.place_btn)

        self.export_btn = QPushButton("Export")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self._on_export)
        btn_row2.addWidget(self.export_btn)

        self.import_btn = QPushButton("Import")
        self.import_btn.clicked.connect(self._on_import)
        btn_row2.addWidget(self.import_btn)
        layout.addLayout(btn_row2)

    def _refresh_guild_list(self):
        self.guild_list.clear()
        for g in guilds.get_all_guilds():
            item = QListWidgetItem(g["name"])
            item.setData(Qt.ItemDataRole.UserRole, g["id"])
            self.guild_list.addItem(item)

    def _on_guild_selected(self, current, previous):
        has_selection = current is not None
        self.delete_btn.setEnabled(has_selection)
        self.dup_btn.setEnabled(has_selection)
        self.place_btn.setEnabled(has_selection)
        self.export_btn.setEnabled(has_selection)
        self.add_member_btn.setEnabled(has_selection)

        if not has_selection:
            self.detail_text.clear()
            self.members_list.clear()
            return

        guild_id = current.data(Qt.ItemDataRole.UserRole)
        guild = guilds.get_guild_by_id(guild_id)
        if not guild:
            return

        lines = [
            f"<b>{guild['name']}</b>",
            f"Center: {guild.get('center_plant_name', 'None')}",
        ]
        if guild.get("description"):
            lines.append(guild["description"])
        lines.append(f"Members: {len(guild.get('members', []))}")
        self.detail_text.setHtml("<br>".join(lines))

        self.members_list.clear()
        for m in guild.get("members", []):
            role = (m.get("role") or "").replace("_", " ")
            text = f"{m['common_name']} — {role} ({m['offset_x']}m, {m['offset_y']}m)"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, m["id"])
            self.members_list.addItem(item)

        self.remove_member_btn.setEnabled(False)
        self.members_list.currentItemChanged.connect(
            lambda c, p: self.remove_member_btn.setEnabled(c is not None)
        )

    def _get_selected_guild_id(self):
        item = self.guild_list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _on_new_guild(self):
        name, ok = QInputDialog.getText(self, "New Guild", "Guild name:")
        if not ok or not name.strip():
            return

        desc, ok = QInputDialog.getText(self, "New Guild", "Description (optional):")
        if not ok:
            desc = ""

        guild_id = guilds.create_guild(name.strip(), desc.strip(), None)
        self._refresh_guild_list()

    def _on_delete_guild(self):
        guild_id = self._get_selected_guild_id()
        if guild_id is None:
            return
        reply = QMessageBox.question(
            self, "Delete Guild", "Delete this guild from the library?"
        )
        if reply == QMessageBox.StandardButton.Yes:
            guilds.delete_guild(guild_id)
            self._refresh_guild_list()

    def _on_duplicate_guild(self):
        guild_id = self._get_selected_guild_id()
        if guild_id:
            guilds.duplicate_guild(guild_id)
            self._refresh_guild_list()

    def _on_add_member(self):
        guild_id = self._get_selected_guild_id()
        if guild_id is None:
            return

        dialog = AddMemberDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            guilds.add_guild_member(
                guild_id, data["plant_id"], data["role"],
                data["offset_x"], data["offset_y"]
            )
            # Re-select to refresh members
            self._on_guild_selected(self.guild_list.currentItem(), None)

    def _on_remove_member(self):
        item = self.members_list.currentItem()
        if item is None:
            return
        member_id = item.data(Qt.ItemDataRole.UserRole)
        guilds.remove_guild_member(member_id)
        self._on_guild_selected(self.guild_list.currentItem(), None)

    def _on_place(self):
        guild_id = self._get_selected_guild_id()
        if guild_id is None:
            return
        guild = guilds.get_guild_by_id(guild_id)
        if guild:
            self.placeGuildRequested.emit(guild)

    def _on_export(self):
        guild_id = self._get_selected_guild_id()
        if guild_id is None:
            return
        data = guilds.export_guild(guild_id)
        if not data:
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Export Guild", f"{data['name']}.guild.json",
            "Guild Files (*.guild.json)"
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            QMessageBox.information(self, "Export", f"Guild exported to {path}")

    def _on_import(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Guild", "", "Guild Files (*.guild.json);;JSON Files (*.json)"
        )
        if not path:
            return

        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            QMessageBox.critical(self, "Import Error", str(e))
            return

        guild_id, warnings = guilds.import_guild(data)
        self._refresh_guild_list()

        if warnings:
            QMessageBox.warning(
                self, "Import Warnings",
                "Guild imported with warnings:\n" + "\n".join(warnings)
            )
        else:
            QMessageBox.information(self, "Import", "Guild imported successfully!")
