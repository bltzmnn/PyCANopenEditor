"""PDO ViewModel，管理 PDO slot 列表、通信参数、映射条目"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QObject, Signal

from ...core.models.eds import EDS
from ...core.models.od_entry import ODentry
from ...core.models.pdo_helper import PDOHelper, PDOSlot, PDOMappingEntry
from ...core.models.datatypes import AccessType, DataType, ObjectType, PDOMappingType


class PDOSlotVM(QObject):
    """单个 PDO 槽位的 ViewModel"""

    def __init__(self, slot: PDOSlot, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._slot = slot

    @property
    def slot(self) -> PDOSlot:
        return self._slot

    @property
    def config_index(self) -> int:
        return self._slot.ConfigurationIndex

    @property
    def config_index_hex(self) -> str:
        return f"0x{self._slot.ConfigurationIndex:04X}"

    @property
    def mapping_index(self) -> int:
        return self._slot.MappingIndex

    @property
    def mapping_index_hex(self) -> str:
        return f"0x{self._slot.MappingIndex:04X}"

    @property
    def cob(self) -> int:
        return self._slot.COB

    @cob.setter
    def cob(self, value: int) -> None:
        self._slot.COB = value

    @property
    def cob_hex(self) -> str:
        return f"0x{self._slot.COB & 0x7FF:03X}"

    @property
    def is_tx(self) -> bool:
        return self._slot.isTXPDO()

    @property
    def is_rx(self) -> bool:
        return self._slot.isRXPDO()

    @property
    def pdo_type_name(self) -> str:
        return "TX PDO" if self.is_tx else "RX PDO"

    @property
    def transmission_type(self) -> int:
        return self._slot.transmissiontype

    @transmission_type.setter
    def transmission_type(self, value: int) -> None:
        self._slot.transmissiontype = value

    @property
    def inhibit(self) -> int:
        return self._slot.inhibit

    @inhibit.setter
    def inhibit(self, value: int) -> None:
        self._slot.inhibit = value

    @property
    def event_timer(self) -> int:
        return self._slot.eventtimer

    @event_timer.setter
    def event_timer(self, value: int) -> None:
        self._slot.eventtimer = value

    @property
    def sync_start(self) -> int:
        return self._slot.syncstart

    @sync_start.setter
    def sync_start(self, value: int) -> None:
        self._slot.syncstart = value

    @property
    def invalid(self) -> bool:
        return self._slot.invalid

    @invalid.setter
    def invalid(self, value: bool) -> None:
        self._slot.invalid = value

    @property
    def nodeid_present(self) -> bool:
        return self._slot.nodeidpresent

    @property
    def total_bits(self) -> int:
        return sum(m.width for m in self._slot.Mapping)

    @property
    def is_over_64bit(self) -> bool:
        return self.total_bits > 64

    @property
    def mapping_count(self) -> int:
        return len(self._slot.Mapping)

    def get_mapping_entries(self) -> list[PDOMappingEntry]:
        """获取映射条目列表"""
        return list(self._slot.Mapping)

    def __str__(self) -> str:
        invalid_mark = " [Invalid]" if self.invalid else ""
        nodeid_mark = " (+NodeID)" if self.nodeid_present else ""
        return f"{self.pdo_type_name} {self.config_index_hex} COB:{self.cob_hex}{nodeid_mark}{invalid_mark}"


class PDOViewModel(QObject):
    """PDO ViewModel，管理 PDO slot 列表、通信参数、映射条目"""

    pdo_list_changed = Signal()
    selected_pdo_changed = Signal(object)  # PDOSlotVM or None
    data_modified = Signal()

    def __init__(self, eds: Optional[EDS] = None, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._eds = eds
        self._helper: Optional[PDOHelper] = None
        self._selected_slot_index: int = -1
        self._filter_mode: str = "all"  # "all", "tx", "rx"

        if eds:
            self._rebuild_helper()

    def set_eds(self, eds: Optional[EDS]) -> None:
        """设置 EDS 数据"""
        self._eds = eds
        self._selected_slot_index = -1
        self._rebuild_helper()
        self.pdo_list_changed.emit()
        self.selected_pdo_changed.emit(None)

    @property
    def eds(self) -> Optional[EDS]:
        return self._eds

    def _rebuild_helper(self) -> None:
        """重建 PDO helper"""
        if self._eds:
            self._helper = PDOHelper(self._eds)
            self._helper.build_PDOlists()
        else:
            self._helper = None

    def set_filter(self, mode: str) -> None:
        """设置过滤模式: "all", "tx", "rx" """
        self._filter_mode = mode
        self.pdo_list_changed.emit()

    def get_pdo_slots(self) -> list[PDOSlotVM]:
        """获取过滤后的 PDO 槽位列表"""
        if self._helper is None:
            return []

        slots = []
        for slot in self._helper.pdoslots:
            if self._filter_mode == "tx" and not slot.isTXPDO():
                continue
            if self._filter_mode == "rx" and not slot.isRXPDO():
                continue
            slots.append(PDOSlotVM(slot, self))

        return slots

    def get_tx_slots(self) -> list[PDOSlotVM]:
        """获取 TX PDO 槽位"""
        if self._helper is None:
            return []
        return [PDOSlotVM(s, self) for s in self._helper.pdoslots if s.isTXPDO()]

    def get_rx_slots(self) -> list[PDOSlotVM]:
        """获取 RX PDO 槽位"""
        if self._helper is None:
            return []
        return [PDOSlotVM(s, self) for s in self._helper.pdoslots if s.isRXPDO()]

    def select_pdo(self, slot_index: int) -> None:
        """选中 PDO 槽位"""
        self._selected_slot_index = slot_index
        slot_vm = self._get_slot_at(slot_index)
        self.selected_pdo_changed.emit(slot_vm)

    def _get_slot_at(self, index: int) -> Optional[PDOSlotVM]:
        """获取指定位置的 PDOSlotVM"""
        slots = self.get_pdo_slots()
        if 0 <= index < len(slots):
            return slots[index]
        return None

    @property
    def selected_pdo(self) -> Optional[PDOSlotVM]:
        """获取当前选中的 PDO 槽位"""
        return self._get_slot_at(self._selected_slot_index)

    def update_comm_param(
        self,
        cob: Optional[int] = None,
        transmission_type: Optional[int] = None,
        inhibit: Optional[int] = None,
        event_timer: Optional[int] = None,
        sync_start: Optional[int] = None,
        invalid: Optional[bool] = None,
    ) -> bool:
        """更新选中 PDO 的通信参数"""
        slot_vm = self.selected_pdo
        if slot_vm is None:
            return False

        changed = False
        if cob is not None and cob != slot_vm.cob:
            slot_vm.cob = cob
            changed = True
        if transmission_type is not None and transmission_type != slot_vm.transmission_type:
            slot_vm.transmission_type = transmission_type
            changed = True
        if inhibit is not None and inhibit != slot_vm.inhibit:
            slot_vm.inhibit = inhibit
            changed = True
        if event_timer is not None and event_timer != slot_vm.event_timer:
            slot_vm.event_timer = event_timer
            changed = True
        if sync_start is not None and sync_start != slot_vm.sync_start:
            slot_vm.sync_start = sync_start
            changed = True
        if invalid is not None and invalid != slot_vm.invalid:
            slot_vm.invalid = invalid
            changed = True

        if changed:
            self._write_back_comm_params(slot_vm)
            self.data_modified.emit()

        return changed

    def _write_back_comm_params(self, slot_vm: PDOSlotVM) -> None:
        """将通信参数写回 EDS 数据"""
        if self._eds is None:
            return

        slot = slot_vm.slot
        config_idx = slot.ConfigurationIndex
        od = self._eds.ods.get(config_idx)
        if od is None:
            return

        # COB (sub 1)
        sub1 = od.Getsubobject(1)
        if sub1:
            cob_val = slot.COB & 0x7FF
            if slot.nodeidpresent:
                sub1.defaultvalue = f"$NODEID+0x{cob_val:03X}"
            else:
                sub1.defaultvalue = f"0x{cob_val:03X}"

        # Transmission type (sub 2)
        sub2 = od.Getsubobject(2)
        if sub2:
            sub2.defaultvalue = str(slot.transmissiontype)

        # Inhibit (sub 3)
        sub3 = od.Getsubobject(3)
        if sub3:
            sub3.defaultvalue = str(slot.inhibit)

        # Event timer (sub 5)
        sub5 = od.Getsubobject(5)
        if sub5:
            sub5.defaultvalue = str(slot.eventtimer)

        self._eds.Dirty = True

    def get_mapping_description(self, entry: PDOMappingEntry) -> str:
        """获取映射条目的描述文本"""
        if entry.entry is None:
            return f"未映射 ({entry.width} bits)"

        od = entry.entry
        return f"0x{od.index:04X}/{od.Subindex:02X} {od.parameter_name} ({entry.width} bits)"

    def get_mapping_total_bits(self) -> int:
        """获取当前选中 PDO 的映射总位数"""
        slot_vm = self.selected_pdo
        if slot_vm is None:
            return 0
        return slot_vm.total_bits

    def rebuild(self) -> None:
        """重建 PDO 列表（在 EDS 数据变化后调用）"""
        self._rebuild_helper()
        self.pdo_list_changed.emit()

    def add_pdo(self, rx: bool, index: int) -> bool:
        """添加 PDO 通信参数和映射 OD 条目，对应 C# CreatePDO"""
        if self._eds is None:
            return False

        # RX: 0x1400-0x15FF, TX: 0x1800-0x19FF
        if rx and not (0x1400 <= index < 0x1600):
            return False
        if not rx and not (0x1800 <= index < 0x1A00):
            return False

        mapping_index = index + 0x200

        if index in self._eds.ods or mapping_index in self._eds.ods:
            return False

        # 创建通信参数 OD
        if rx:
            comm_name = "RPDO communication parameter"
            mapping_name = "RPDO mapping parameter"
            cob_default = "$NODEID+0x200"
            max_sub = "2"
        else:
            comm_name = "TPDO communication parameter"
            mapping_name = "TPDO mapping parameter"
            cob_default = "$NODEID+0x180"
            max_sub = "6"

        od_comparam = ODentry(
            parameter_name=comm_name,
            index=index,
            objecttype=ObjectType.RECORD,
            accesstype=AccessType.RO,
            pdo_type=PDOMappingType.NO,
        )
        od_comparam.prop.CO_storageGroup = "ROM"

        # sub 0: max sub-index
        od_comparam.subobjects[0] = ODentry(
            parameter_name="max sub-index",
            datatype=DataType.UNSIGNED8,
            defaultvalue=max_sub,
            accesstype=AccessType.RO,
            pdo_type=PDOMappingType.NO,
            parent=od_comparam,
        )
        # sub 1: COB-ID
        cob_label = "COB-ID used by RPDO" if rx else "COB-ID used by TPDO"
        od_comparam.subobjects[1] = ODentry(
            parameter_name=cob_label,
            datatype=DataType.UNSIGNED32,
            defaultvalue=cob_default,
            accesstype=AccessType.RW,
            pdo_type=PDOMappingType.NO,
            parent=od_comparam,
        )
        # sub 2: transmission type
        od_comparam.subobjects[2] = ODentry(
            parameter_name="transmission type",
            datatype=DataType.UNSIGNED8,
            defaultvalue="254",
            accesstype=AccessType.RW,
            pdo_type=PDOMappingType.NO,
            parent=od_comparam,
        )

        if not rx:
            # sub 3: inhibit time
            od_comparam.subobjects[3] = ODentry(
                parameter_name="inhibit time",
                datatype=DataType.UNSIGNED16,
                defaultvalue="0",
                accesstype=AccessType.RW,
                pdo_type=PDOMappingType.NO,
                parent=od_comparam,
            )
            # sub 5: event timer
            od_comparam.subobjects[5] = ODentry(
                parameter_name="event timer",
                datatype=DataType.UNSIGNED16,
                defaultvalue="0",
                accesstype=AccessType.RW,
                pdo_type=PDOMappingType.NO,
                parent=od_comparam,
            )
            # sub 6: SYNC start value
            od_comparam.subobjects[6] = ODentry(
                parameter_name="SYNC start value",
                datatype=DataType.UNSIGNED8,
                defaultvalue="0",
                accesstype=AccessType.RW,
                pdo_type=PDOMappingType.NO,
                parent=od_comparam,
            )

        # 创建映射 OD
        od_mapping = ODentry(
            parameter_name=mapping_name,
            index=mapping_index,
            objecttype=ObjectType.RECORD,
            accesstype=AccessType.RW,
            pdo_type=PDOMappingType.NO,
        )
        od_mapping.prop.CO_storageGroup = "ROM"

        od_mapping.subobjects[0] = ODentry(
            parameter_name="Number of mapped objects",
            datatype=DataType.UNSIGNED8,
            defaultvalue="0",
            accesstype=AccessType.RO,
            pdo_type=PDOMappingType.NO,
            parent=od_mapping,
        )

        for p in range(1, 9):
            od_mapping.subobjects[p] = ODentry(
                parameter_name=f"mapped object {p}",
                datatype=DataType.UNSIGNED32,
                defaultvalue="0x00000000",
                accesstype=AccessType.RO,
                pdo_type=PDOMappingType.NO,
                parent=od_mapping,
            )

        self._eds.ods[index] = od_comparam
        self._eds.ods[mapping_index] = od_mapping
        self._eds.Dirty = True
        self._eds.UpdatePDOcount()

        self._rebuild_helper()
        self.pdo_list_changed.emit()
        self.data_modified.emit()

        return True

    def delete_pdo(self, config_index: int) -> bool:
        """删除 PDO 通信参数和映射 OD 条目"""
        if self._eds is None:
            return False

        mapping_index = config_index + 0x200

        if config_index not in self._eds.ods:
            return False

        del self._eds.ods[config_index]
        if mapping_index in self._eds.ods:
            del self._eds.ods[mapping_index]

        self._eds.Dirty = True
        self._eds.UpdatePDOcount()

        self._selected_slot_index = -1
        self.selected_pdo_changed.emit(None)

        self._rebuild_helper()
        self.pdo_list_changed.emit()
        self.data_modified.emit()

        return True

    def find_next_pdo_index(self, rx: bool) -> Optional[int]:
        """找到下一个可用的 PDO 通信参数 index"""
        if self._eds is None:
            return None

        if rx:
            for idx in range(0x1400, 0x1600):
                if idx not in self._eds.ods:
                    return idx
        else:
            for idx in range(0x1800, 0x1A00):
                if idx not in self._eds.ods:
                    return idx

        return None

    def add_mapping(self, od_index: int, sub_index: int, bits: int) -> bool:
        """添加映射条目到当前选中的 PDO"""
        if self._eds is None:
            return False

        slot_vm = self.selected_pdo
        if slot_vm is None:
            return False

        slot = slot_vm.slot
        total_bits = sum(m.width for m in slot.Mapping)
        if total_bits + bits > 64:
            return False

        mapping_index = slot.MappingIndex
        mapping_od = self._eds.ods.get(mapping_index)
        if mapping_od is None:
            return False

        # 检查映射位置数量
        def _is_mapped(s):
            if s.Subindex == 0:
                return False
            try:
                return int(s.defaultvalue, 0) != 0
            except (ValueError, TypeError):
                return False

        num_mapped = len([s for s in mapping_od.subobjects.values() if _is_mapped(s)])
        next_sub = num_mapped + 1

        if next_sub > 8:
            return False

        # 写入映射值
        map_val = (od_index << 16) | (sub_index << 8) | bits
        sub_od = mapping_od.subobjects.get(next_sub)
        if sub_od:
            sub_od.defaultvalue = f"0x{map_val:08X}"
        else:
            new_sub = ODentry(
                parameter_name=f"mapped object {next_sub}",
                datatype=DataType.UNSIGNED32,
                defaultvalue=f"0x{map_val:08X}",
                accesstype=AccessType.RO,
                pdo_type=PDOMappingType.NO,
                parent=mapping_od,
            )
            mapping_od.subobjects[next_sub] = new_sub

        # 更新映射数量
        sub0 = mapping_od.subobjects.get(0)
        if sub0:
            sub0.defaultvalue = str(next_sub)

        self._eds.Dirty = True

        self._rebuild_helper()
        self.pdo_list_changed.emit()
        self.data_modified.emit()

        return True

    def delete_mapping(self, mapping_ordinal: int) -> bool:
        """删除映射条目（1-based ordinal）"""
        if self._eds is None:
            return False

        slot_vm = self.selected_pdo
        if slot_vm is None:
            return False

        mapping_index = slot_vm.slot.MappingIndex
        mapping_od = self._eds.ods.get(mapping_index)
        if mapping_od is None:
            return False

        if mapping_ordinal not in mapping_od.subobjects:
            return False

        # 清除映射值
        mapping_od.subobjects[mapping_ordinal].defaultvalue = "0x00000000"

        # 重新排列：把后面的往前移
        new_subobjects: dict[int, ODentry] = {}
        new_idx = 0
        sub0 = mapping_od.subobjects.get(0)
        if sub0:
            new_subobjects[0] = sub0

        for sub_idx in sorted(mapping_od.subobjects.keys()):
            if sub_idx == 0:
                continue
            val = mapping_od.subobjects[sub_idx].defaultvalue
            try:
                is_nonzero = val and int(val, 0) != 0
            except (ValueError, TypeError):
                is_nonzero = False
            if is_nonzero:
                new_idx += 1
                new_subobjects[new_idx] = mapping_od.subobjects[sub_idx]
                if new_idx != sub_idx:
                    new_subobjects[new_idx].parameter_name = f"mapped object {new_idx}"

        # 补齐空的 sub 位置到 8
        for i in range(new_idx + 1, 9):
            if i in mapping_od.subobjects:
                new_subobjects[i] = mapping_od.subobjects[i]
                new_subobjects[i].defaultvalue = "0x00000000"
                new_subobjects[i].parameter_name = f"mapped object {i}"

        mapping_od.subobjects = new_subobjects

        # 更新映射数量
        if 0 in mapping_od.subobjects:
            mapping_od.subobjects[0].defaultvalue = str(new_idx)

        self._eds.Dirty = True

        self._rebuild_helper()
        self.pdo_list_changed.emit()
        self.data_modified.emit()

        return True

    def get_mappable_objects(self) -> list[tuple[int, int, str, int]]:
        """获取可映射的 OD 对象列表，返回 (index, subindex, name, bits)"""
        if self._eds is None:
            return []

        result = []
        for idx, od in sorted(self._eds.ods.items()):
            if idx < 0x1000:
                continue
            if od.prop.CO_disabled:
                continue
            if not od.PDOMapping:
                continue

            if od.objecttype == ObjectType.VAR:
                bits = od.sizeof_datatype()
                if bits > 0:
                    result.append((idx, 0, od.parameter_name, bits))
            elif od.objecttype in (ObjectType.ARRAY, ObjectType.RECORD):
                for sub_idx, sub_od in sorted(od.subobjects.items()):
                    if sub_idx == 0:
                        continue
                    if not sub_od.PDOMapping:
                        continue
                    bits = sub_od.sizeof_datatype()
                    if bits > 0:
                        result.append((idx, sub_idx, sub_od.parameter_name, bits))

        return result
