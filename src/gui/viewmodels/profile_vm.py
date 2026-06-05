"""Profile ViewModel，扫描 profiles/ 目录、加载 XPD/XDD 文件、合并到设备"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

from PySide6.QtCore import QObject, Signal

from ...core.models.eds import EDS
from ...core.models.od_entry import ODentry
from ...core.models.datatypes import ObjectType


@dataclass
class MergeEntry:
    """合并条目，表示一个要导入的 OD 条目及其冲突状态"""
    index: int
    name: str
    object_type: ObjectType
    collision: bool = False
    insert: bool = True
    offset: int = 0


@dataclass
class ProfileInfo:
    """Profile 文件信息"""
    filepath: str
    filename: str
    eds: Optional[EDS] = None
    error: str = ""


class ProfileViewModel(QObject):
    """Profile 管理器 ViewModel"""

    profiles_loaded = Signal()
    merge_preview_ready = Signal()
    merge_completed = Signal(bool)
    status_message = Signal(str)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._profiles: list[ProfileInfo] = []
        self._merge_entries: list[MergeEntry] = []
        self._selected_profile: Optional[ProfileInfo] = None
        self._target_eds: Optional[EDS] = None

    def scan_profiles(self, profile_dir: str) -> list[ProfileInfo]:
        """扫描指定目录中的 XPD/XDD 文件"""
        self._profiles.clear()

        if not os.path.isdir(profile_dir):
            self.status_message.emit(f"Profile 目录不存在: {profile_dir}")
            return []

        for filename in sorted(os.listdir(profile_dir)):
            ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            if ext not in ("xpd", "xdd", "xdc"):
                continue

            filepath = os.path.join(profile_dir, filename)
            info = ProfileInfo(filepath=filepath, filename=filename)

            try:
                if ext in ("xpd", "xdd", "xdc"):
                    from ...core.parsers.xdd_handler import XDDHandler
                    handler = XDDHandler()
                    result = handler.read_xml(filepath)
                    if result is not None:
                        info.eds = result
                    else:
                        info.error = "无法解析文件"
            except Exception as e:
                info.error = str(e)

            self._profiles.append(info)

        self.profiles_loaded.emit()
        return self._profiles

    @property
    def profiles(self) -> list[ProfileInfo]:
        return self._profiles

    @property
    def merge_entries(self) -> list[MergeEntry]:
        return self._merge_entries

    def set_target(self, eds: Optional[EDS]) -> None:
        """设置目标设备 EDS"""
        self._target_eds = eds

    def select_profile(self, profile: ProfileInfo) -> None:
        """选择要导入的 Profile"""
        self._selected_profile = profile

    def preview_merge(self, offset: int = 0) -> list[MergeEntry]:
        """预览合并结果，检测冲突"""
        if self._selected_profile is None or self._selected_profile.eds is None:
            self._merge_entries.clear()
            self.merge_preview_ready.emit()
            return []

        if self._target_eds is None:
            self._merge_entries.clear()
            self.merge_preview_ready.emit()
            return []

        profile_eds = self._selected_profile.eds
        entries = []

        for idx, od in sorted(profile_eds.ods.items()):
            adjusted_idx = idx + offset
            collision = adjusted_idx in self._target_eds.ods

            entry = MergeEntry(
                index=adjusted_idx,
                name=od.parameter_name,
                object_type=od.objecttype,
                collision=collision,
                insert=not collision,
                offset=offset,
            )
            entries.append(entry)

        self._merge_entries = entries
        self.merge_preview_ready.emit()
        return entries

    def execute_merge(self, skip_collisions: bool = True) -> bool:
        """执行合并，将 Profile 中的 OD 条目导入到目标设备"""
        if self._selected_profile is None or self._selected_profile.eds is None:
            return False

        if self._target_eds is None:
            return False

        profile_eds = self._selected_profile.eds
        merged_count = 0
        skipped_count = 0

        for entry in self._merge_entries:
            if not entry.insert:
                skipped_count += 1
                continue

            idx = entry.index
            original_idx = idx - entry.offset

            if idx in self._target_eds.ods:
                if skip_collisions:
                    skipped_count += 1
                    continue
                # 覆盖现有条目
                del self._target_eds.ods[idx]

            # 克隆 OD 条目并调整 index
            if original_idx in profile_eds.ods:
                new_od = profile_eds.ods[original_idx].clone()
                new_od._index = idx
                # 调整 sub-objects 的 parent index
                for sub_idx, sub_od in new_od.subobjects.items():
                    sub_od._index = idx
                self._target_eds.ods[idx] = new_od
                merged_count += 1

        self._target_eds.Dirty = True
        self._target_eds.UpdatePDOcount()

        self.status_message.emit(
            f"合并完成: {merged_count} 条目导入, {skipped_count} 跳过"
        )
        self.merge_completed.emit(True)
        return True

    def get_conflict_count(self) -> int:
        """获取冲突数量"""
        return sum(1 for e in self._merge_entries if e.collision)

    def get_insert_count(self) -> int:
        """获取将要导入的数量"""
        return sum(1 for e in self._merge_entries if e.insert)

    def toggle_entry(self, index: int, insert: bool) -> None:
        """切换单个条目的导入状态"""
        for entry in self._merge_entries:
            if entry.index == index:
                entry.insert = insert
                break
