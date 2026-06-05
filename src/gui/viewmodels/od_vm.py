"""对象字典 ViewModel，管理 OD 树选中、添加/删除 entry、sub-object 编辑"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QObject, Signal, Slot

from ...core.models.eds import EDS
from ...core.models.od_entry import ODentry
from ...core.models.datatypes import DataType, ObjectType, AccessType, PDOMappingType


class ODItemVM(QObject):
    """单个 OD 条目的 ViewModel，用于列表显示"""
    name_changed = Signal()

    def __init__(self, od: ODentry, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._od = od

    @property
    def od(self) -> ODentry:
        return self._od

    @property
    def index(self) -> int:
        return self._od.index

    @property
    def index_hex(self) -> str:
        return f"0x{self._od.index:04X}"

    @property
    def name(self) -> str:
        return self._od.parameter_name

    @property
    def object_type(self) -> str:
        return self._od.objecttype_string()

    @property
    def data_type(self) -> str:
        dt = self._od.datatype
        return dt.name if dt != DataType.UNKNOWN else ""

    def __str__(self) -> str:
        disabled_mark = " [disabled]" if self._od.prop.CO_disabled else ""
        return f"{self.index_hex} - {self.name} ({self.object_type}, {self.data_type}){disabled_mark}"


class SubObjectVM(QObject):
    """Sub-object 的 ViewModel"""
    data_changed = Signal()

    def __init__(self, od: ODentry, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._od = od

    @property
    def od(self) -> ODentry:
        return self._od

    @property
    def subindex(self) -> int:
        return self._od.Subindex

    @property
    def subindex_hex(self) -> str:
        return f"0x{self._od.Subindex:02X}"

    @property
    def name(self) -> str:
        return self._od.parameter_name

    @name.setter
    def name(self, value: str) -> None:
        self._od.parameter_name = value
        self.data_changed.emit()

    @property
    def data_type(self) -> DataType:
        return self._od.datatype

    @data_type.setter
    def data_type(self, value: DataType) -> None:
        self._od.datatype = value
        self.data_changed.emit()

    @property
    def data_type_name(self) -> str:
        dt = self._od.datatype
        return dt.name if dt != DataType.UNKNOWN else ""

    @property
    def default_value(self) -> str:
        return self._od.defaultvalue

    @default_value.setter
    def default_value(self, value: str) -> None:
        self._od.defaultvalue = value
        self.data_changed.emit()

    @property
    def access_type(self) -> AccessType:
        return self._od.accesstype

    @access_type.setter
    def access_type(self, value: AccessType) -> None:
        self._od.accesstype = value
        self.data_changed.emit()

    @property
    def pdo_type(self) -> PDOMappingType:
        return self._od.PDOtype

    @pdo_type.setter
    def pdo_type(self, value: PDOMappingType) -> None:
        self._od.PDOtype = value
        self.data_changed.emit()

    @property
    def disabled(self) -> bool:
        return self._od.prop.CO_disabled

    @disabled.setter
    def disabled(self, value: bool) -> None:
        self._od.prop.CO_disabled = value
        self.data_changed.emit()

    @property
    def description(self) -> str:
        return self._od.Description

    @description.setter
    def description(self, value: str) -> None:
        self._od.Description = value
        self.data_changed.emit()


class ODViewModel(QObject):
    """对象字典 ViewModel，管理 OD 树选中、添加/删除 entry、sub-object 编辑"""

    # 信号
    selected_object_changed = Signal(object)  # ODItemVM or None
    selected_subobject_changed = Signal(object)  # SubObjectVM or None
    subobjects_changed = Signal()  # sub-object 列表变化
    od_list_changed = Signal()  # OD 列表变化
    data_modified = Signal()  # 数据被修改

    def __init__(self, eds: Optional[EDS] = None, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._eds = eds
        self._selected_index: Optional[int] = None
        self._selected_subindex: Optional[int] = None
        self._filter_min: int = 0x0000
        self._filter_max: int = 0xFFFF

    def set_eds(self, eds: Optional[EDS]) -> None:
        """设置 EDS 数据"""
        self._eds = eds
        self._selected_index = None
        self._selected_subindex = None
        self.selected_object_changed.emit(None)
        self.selected_subobject_changed.emit(None)
        self.od_list_changed.emit()

    @property
    def eds(self) -> Optional[EDS]:
        return self._eds

    def set_filter(self, min_index: int, max_index: int) -> None:
        """设置 index 范围过滤器"""
        self._filter_min = min_index
        self._filter_max = max_index
        self.od_list_changed.emit()

    def get_filtered_items(self) -> list[ODItemVM]:
        """获取过滤后的 OD 条目列表"""
        if self._eds is None:
            return []

        items = []
        for idx, od in sorted(self._eds.ods.items()):
            if not (self._filter_min <= idx <= self._filter_max):
                continue
            items.append(ODItemVM(od, self))
        return items

    def select_object(self, index: int) -> None:
        """选中一个 OD 条目"""
        if self._eds is None:
            return

        self._selected_index = index
        self._selected_subindex = None

        od = self._eds.ods.get(index)
        if od:
            self.selected_object_changed.emit(ODItemVM(od, self))
            # 默认选中 subindex 0
            if od.subobjects and 0 in od.subobjects:
                self.select_subobject(0)
            else:
                self.selected_subobject_changed.emit(None)
        else:
            self.selected_object_changed.emit(None)
            self.selected_subobject_changed.emit(None)

        self.subobjects_changed.emit()

    def select_subobject(self, subindex: int) -> None:
        """选中一个 sub-object"""
        if self._eds is None or self._selected_index is None:
            return

        od = self._eds.ods.get(self._selected_index)
        if od is None:
            return

        sub_od = od.subobjects.get(subindex) if subindex > 0 else od
        if sub_od:
            self._selected_subindex = subindex
            self.selected_subobject_changed.emit(SubObjectVM(sub_od, self))
        else:
            self._selected_subindex = None
            self.selected_subobject_changed.emit(None)

    def get_subobjects(self) -> list[SubObjectVM]:
        """获取当前选中 OD 条目的所有 sub-objects"""
        if self._eds is None or self._selected_index is None:
            return []

        od = self._eds.ods.get(self._selected_index)
        if od is None:
            return []

        # 对于 VAR 类型，返回自身作为唯一的 sub-object
        if od.objecttype == ObjectType.VAR or not od.subobjects:
            return [SubObjectVM(od, self)]

        # 对于 ARRAY/RECORD 类型，返回所有 sub-objects
        items = []
        for sub_idx in sorted(od.subobjects.keys()):
            sub_od = od.subobjects[sub_idx]
            items.append(SubObjectVM(sub_od, self))
        return items

    @property
    def selected_object(self) -> Optional[ODItemVM]:
        """获取当前选中的 OD 条目"""
        if self._eds is None or self._selected_index is None:
            return None
        od = self._eds.ods.get(self._selected_index)
        return ODItemVM(od, self) if od else None

    @property
    def selected_subobject(self) -> Optional[SubObjectVM]:
        """获取当前选中的 sub-object"""
        if self._eds is None or self._selected_index is None:
            return None

        od = self._eds.ods.get(self._selected_index)
        if od is None:
            return None

        if self._selected_subindex is None or self._selected_subindex == 0:
            return SubObjectVM(od, self)

        sub_od = od.subobjects.get(self._selected_subindex)
        return SubObjectVM(sub_od, self) if sub_od else None

    def add_od_entry(self, index: int, name: str, object_type: ObjectType) -> Optional[ODentry]:
        """添加新的 OD 条目"""
        if self._eds is None:
            return None

        if index in self._eds.ods:
            return None

        # 创建新的 OD 条目
        od = ODentry(
            parameter_name=name,
            index=index,
            objecttype=object_type,
            datatype=DataType.UNSIGNED32,
            accesstype=AccessType.RW,
        )

        # 对于 ARRAY/RECORD 类型，添加 sub-index 0
        if object_type in (ObjectType.ARRAY, ObjectType.RECORD):
            sub0 = ODentry(
                parameter_name="Highest sub-index supported",
                objecttype=ObjectType.VAR,
                datatype=DataType.UNSIGNED8,
                accesstype=AccessType.RO,
                defaultvalue="0x01",
                parent=od,
            )
            # 添加第一个元素
            sub1 = ODentry(
                parameter_name="Sub Object 1",
                objecttype=ObjectType.VAR,
                datatype=DataType.UNSIGNED32,
                accesstype=AccessType.RW,
                defaultvalue="0",
                parent=od,
            )
            od.subobjects[0] = sub0
            od.subobjects[1] = sub1

        self._eds.ods[index] = od
        self._eds.Dirty = True

        self.od_list_changed.emit()
        self.data_modified.emit()

        return od

    def delete_od_entry(self, index: int) -> bool:
        """删除 OD 条目"""
        if self._eds is None:
            return False

        if index not in self._eds.ods:
            return False

        del self._eds.ods[index]
        self._eds.Dirty = True

        if self._selected_index == index:
            self._selected_index = None
            self._selected_subindex = None
            self.selected_object_changed.emit(None)
            self.selected_subobject_changed.emit(None)

        self.od_list_changed.emit()
        self.data_modified.emit()

        return True

    def add_subobject(self) -> Optional[ODentry]:
        """添加 sub-object 到当前选中的 OD 条目"""
        if self._eds is None or self._selected_index is None:
            return None

        od = self._eds.ods.get(self._selected_index)
        if od is None:
            return None

        new_sub = od.AddSubEntry()
        if new_sub:
            self._eds.Dirty = True
            self.subobjects_changed.emit()
            self.data_modified.emit()

        return new_sub

    def delete_subobject(self, subindex: int, renumber: bool = True) -> bool:
        """删除 sub-object"""
        if self._eds is None or self._selected_index is None:
            return False

        od = self._eds.ods.get(self._selected_index)
        if od is None:
            return False

        sub_od = od.subobjects.get(subindex)
        if sub_od is None:
            return False

        result = sub_od.RemoveSubEntry(renumber)
        if result:
            self._eds.Dirty = True
            self.subobjects_changed.emit()
            self.data_modified.emit()

            if self._selected_subindex == subindex:
                self._selected_subindex = None
                self.selected_subobject_changed.emit(None)

        return result

    def update_subobject(
        self,
        name: Optional[str] = None,
        data_type: Optional[DataType] = None,
        default_value: Optional[str] = None,
        access_type: Optional[AccessType] = None,
        pdo_type: Optional[PDOMappingType] = None,
        description: Optional[str] = None,
        disabled: Optional[bool] = None,
    ) -> bool:
        """更新当前选中的 sub-object 属性"""
        sub = self.selected_subobject
        if sub is None:
            return False

        changed = False
        if name is not None and name != sub.name:
            sub.name = name
            changed = True
        if data_type is not None and data_type != sub.data_type:
            sub.data_type = data_type
            changed = True
        if default_value is not None and default_value != sub.default_value:
            sub.default_value = default_value
            changed = True
        if access_type is not None and access_type != sub.access_type:
            sub.access_type = access_type
            changed = True
        if pdo_type is not None and pdo_type != sub.pdo_type:
            sub.pdo_type = pdo_type
            changed = True
        if description is not None and description != sub.description:
            sub.description = description
            changed = True
        if disabled is not None and disabled != sub.disabled:
            sub.disabled = disabled
            changed = True

        if changed:
            self._eds.Dirty = True
            self.data_modified.emit()

        return changed
