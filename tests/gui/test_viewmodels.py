"""GUI ViewModel 测试"""
import os
import tempfile

import pytest

from src.core.models.eds import EDS
from src.core.models.datatypes import DataType, AccessType, ObjectType, PDOMappingType
from src.core.models.od_entry import ODentry
from src.gui.viewmodels.main_window_vm import MainWindowVM, DeviceVM
from src.gui.viewmodels.device_info_vm import DeviceInfoVM
from src.gui.viewmodels.od_vm import ODViewModel, ODItemVM, SubObjectVM
from src.gui.viewmodels.pdo_vm import PDOViewModel, PDOSlotVM
from src.gui.viewmodels.profile_vm import ProfileViewModel, ProfileInfo


class TestDeviceVM:
    def test_name_from_eds(self):
        eds = EDS()
        eds.di.ProductName = "TestDevice"
        vm = DeviceVM(eds)
        assert vm.name == "TestDevice"

    def test_dirty_flag(self):
        eds = EDS()
        vm = DeviceVM(eds)
        assert not vm.dirty
        vm.dirty = True
        assert vm.dirty

    def test_str_representation(self):
        eds = EDS()
        eds.di.ProductName = "MyDev"
        vm = DeviceVM(eds)
        assert str(vm) == "MyDev"
        vm.dirty = True
        assert str(vm) == "MyDev *"


class TestMainWindowVM:
    def test_new_device(self):
        vm = MainWindowVM()
        dev = vm.new_device()
        assert len(vm.devices) == 1
        assert "新设备" in dev.name
        assert vm.current_device is dev

    def test_multiple_devices(self):
        vm = MainWindowVM()
        vm.new_device()
        vm.new_device()
        vm.new_device()
        assert len(vm.devices) == 3

    def test_switch_device(self):
        vm = MainWindowVM()
        d1 = vm.new_device()
        d2 = vm.new_device()
        vm.current_index = 0
        assert vm.current_device is d1
        vm.current_index = 1
        assert vm.current_device is d2

    def test_close_device(self):
        vm = MainWindowVM()
        vm.new_device()
        vm.new_device()
        vm.close_device(0)
        assert len(vm.devices) == 1

    def test_open_eds_file(self):
        eds = EDS()
        od = ODentry(
            parameter_name="Device type",
            index=0x1000,
            datatype=DataType.UNSIGNED32,
            defaultvalue="0x00000000",
            accesstype=AccessType.RO,
        )
        eds.ods[0x1000] = od

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test.eds")
            eds.Savefile(filepath)

            vm = MainWindowVM()
            dev = vm.open_file(filepath)
            assert dev is not None
            assert 0x1000 in dev.eds.ods

    def test_save_file(self):
        vm = MainWindowVM()
        dev = vm.new_device()
        dev.eds.di.ProductName = "SaveTest"

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "output.eds")
            assert vm.save_file(filepath)
            assert os.path.exists(filepath)

    def test_export_file(self):
        vm = MainWindowVM()
        dev = vm.new_device()

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "output.md")
            assert vm.export_file(filepath, "Documentation Markup")
            assert os.path.exists(filepath)

    def test_current_device_none_initially(self):
        vm = MainWindowVM()
        assert vm.current_device is None

    def test_close_last_device(self):
        vm = MainWindowVM()
        vm.new_device()
        vm.close_device(0)
        assert vm.current_device is None


class TestDeviceInfoVM:
    def test_get_fields(self):
        eds = EDS()
        eds.di.VendorName = "TestVendor"
        eds.di.ProductName = "TestProduct"
        vm = DeviceInfoVM(eds)
        assert vm.vendor_name == "TestVendor"
        assert vm.product_name == "TestProduct"

    def test_set_fields(self):
        eds = EDS()
        vm = DeviceInfoVM(eds)
        vm.vendor_name = "NewVendor"
        vm.product_name = "NewProduct"
        assert eds.di.VendorName == "NewVendor"
        assert eds.di.ProductName == "NewProduct"

    def test_none_eds(self):
        vm = DeviceInfoVM(None)
        assert vm.vendor_name == ""


class TestODViewModel:
    """ODViewModel 测试"""

    def _make_eds_with_entries(self):
        """创建包含 OD 条目的 EDS"""
        eds = EDS()

        # 通信对象
        od_1000 = ODentry(
            parameter_name="Device type",
            index=0x1000,
            datatype=DataType.UNSIGNED32,
            defaultvalue="0x00000000",
            accesstype=AccessType.RO,
        )
        eds.ods[0x1000] = od_1000

        # 制造商对象
        od_2000 = ODentry(
            parameter_name="Manufacturer device name",
            index=0x2000,
            datatype=DataType.VISIBLE_STRING,
            defaultvalue="$00",
            accesstype=AccessType.RO,
        )
        eds.ods[0x2000] = od_2000

        # 带 sub-objects 的 RECORD 类型
        od_1018 = ODentry(
            parameter_name="Identity object",
            index=0x1018,
            objecttype=ObjectType.RECORD,
            datatype=DataType.UNKNOWN,
        )
        sub0 = ODentry(
            parameter_name="Number of entries",
            index=0x1018,
            objecttype=ObjectType.VAR,
            datatype=DataType.UNSIGNED8,
            defaultvalue="0x04",
            accesstype=AccessType.RO,
            parent=od_1018,
        )
        sub1 = ODentry(
            parameter_name="Vendor ID",
            index=0x1018,
            objecttype=ObjectType.VAR,
            datatype=DataType.UNSIGNED32,
            defaultvalue="0x00000000",
            accesstype=AccessType.RO,
            parent=od_1018,
        )
        od_1018.subobjects[0] = sub0
        od_1018.subobjects[1] = sub1
        eds.ods[0x1018] = od_1018

        return eds

    def test_set_eds(self):
        eds = self._make_eds_with_entries()
        vm = ODViewModel()
        vm.set_eds(eds)
        assert vm.eds is eds

    def test_get_filtered_items_comm(self):
        eds = self._make_eds_with_entries()
        vm = ODViewModel(eds)
        vm.set_filter(0x1000, 0x1FFF)
        items = vm.get_filtered_items()
        assert len(items) >= 2
        indices = [item.index for item in items]
        assert 0x1000 in indices
        assert 0x1018 in indices

    def test_get_filtered_items_mfr(self):
        eds = self._make_eds_with_entries()
        vm = ODViewModel(eds)
        vm.set_filter(0x2000, 0x5FFF)
        items = vm.get_filtered_items()
        assert len(items) == 1
        assert items[0].index == 0x2000

    def test_select_object(self):
        eds = self._make_eds_with_entries()
        vm = ODViewModel(eds)
        vm.select_object(0x1018)
        obj = vm.selected_object
        assert obj is not None
        assert obj.index == 0x1018

    def test_select_subobject(self):
        eds = self._make_eds_with_entries()
        vm = ODViewModel(eds)
        vm.select_object(0x1018)
        vm.select_subobject(1)
        sub = vm.selected_subobject
        assert sub is not None
        assert sub.name == "Vendor ID"

    def test_get_subobjects_record(self):
        eds = self._make_eds_with_entries()
        vm = ODViewModel(eds)
        vm.select_object(0x1018)
        subs = vm.get_subobjects()
        assert len(subs) == 2

    def test_add_od_entry_var(self):
        eds = self._make_eds_with_entries()
        vm = ODViewModel(eds)
        od = vm.add_od_entry(0x2100, "Test VAR", ObjectType.VAR)
        assert od is not None
        assert 0x2100 in eds.ods
        assert od.objecttype == ObjectType.VAR

    def test_add_od_entry_record(self):
        eds = self._make_eds_with_entries()
        vm = ODViewModel(eds)
        od = vm.add_od_entry(0x2100, "Test RECORD", ObjectType.RECORD)
        assert od is not None
        assert 0x2100 in eds.ods
        assert od.objecttype == ObjectType.RECORD
        assert len(od.subobjects) == 2

    def test_add_od_entry_duplicate(self):
        eds = self._make_eds_with_entries()
        vm = ODViewModel(eds)
        od = vm.add_od_entry(0x1000, "Duplicate", ObjectType.VAR)
        assert od is None

    def test_delete_od_entry(self):
        eds = self._make_eds_with_entries()
        vm = ODViewModel(eds)
        result = vm.delete_od_entry(0x2000)
        assert result is True
        assert 0x2000 not in eds.ods

    def test_delete_od_entry_not_found(self):
        eds = self._make_eds_with_entries()
        vm = ODViewModel(eds)
        result = vm.delete_od_entry(0x9999)
        assert result is False

    def test_add_subobject(self):
        eds = self._make_eds_with_entries()
        vm = ODViewModel(eds)
        vm.select_object(0x1018)
        new_sub = vm.add_subobject()
        assert new_sub is not None
        subs = vm.get_subobjects()
        assert len(subs) > 2

    def test_delete_subobject(self):
        eds = self._make_eds_with_entries()
        vm = ODViewModel(eds)
        vm.select_object(0x1018)
        result = vm.delete_subobject(1)
        assert result is True

    def test_update_subobject_name(self):
        eds = self._make_eds_with_entries()
        vm = ODViewModel(eds)
        vm.select_object(0x1018)
        vm.select_subobject(1)
        vm.update_subobject(name="NewVendorID")
        sub = vm.selected_subobject
        assert sub.name == "NewVendorID"

    def test_update_subobject_datatype(self):
        eds = self._make_eds_with_entries()
        vm = ODViewModel(eds)
        vm.select_object(0x1018)
        vm.select_subobject(1)
        vm.update_subobject(data_type=DataType.UNSIGNED16)
        sub = vm.selected_subobject
        assert sub.data_type == DataType.UNSIGNED16

    def test_none_eds(self):
        vm = ODViewModel(None)
        assert vm.eds is None
        assert vm.selected_object is None
        assert vm.selected_subobject is None
        assert vm.get_filtered_items() == []
        assert vm.get_subobjects() == []

    def test_od_item_vm_str(self):
        eds = self._make_eds_with_entries()
        od = eds.ods[0x1000]
        item = ODItemVM(od)
        text = str(item)
        assert "0x1000" in text
        assert "Device type" in text


class TestPDOViewModel:
    """PDOViewModel 测试"""

    def _make_eds_with_pdo(self):
        """创建包含 PDO 配置的 EDS"""
        eds = EDS()

        # TX PDO 通信参数 (0x1800)
        od_1800 = ODentry(
            parameter_name="TPDO communication parameter",
            index=0x1800,
            objecttype=ObjectType.RECORD,
        )
        sub0 = ODentry(
            parameter_name="Number of entries",
            index=0x1800,
            datatype=DataType.UNSIGNED8,
            defaultvalue="0x05",
            accesstype=AccessType.RO,
            parent=od_1800,
        )
        sub1 = ODentry(
            parameter_name="COB-ID",
            index=0x1800,
            datatype=DataType.UNSIGNED32,
            defaultvalue="0x00000180",
            accesstype=AccessType.RW,
            parent=od_1800,
        )
        sub2 = ODentry(
            parameter_name="Transmission type",
            index=0x1800,
            datatype=DataType.UNSIGNED8,
            defaultvalue="254",
            accesstype=AccessType.RW,
            parent=od_1800,
        )
        sub5 = ODentry(
            parameter_name="Event timer",
            index=0x1800,
            datatype=DataType.UNSIGNED16,
            defaultvalue="0",
            accesstype=AccessType.RW,
            parent=od_1800,
        )
        od_1800.subobjects[0] = sub0
        od_1800.subobjects[1] = sub1
        od_1800.subobjects[2] = sub2
        od_1800.subobjects[5] = sub5
        eds.ods[0x1800] = od_1800

        # TX PDO 映射 (0x1A00)
        od_1a00 = ODentry(
            parameter_name="TPDO mapping",
            index=0x1A00,
            objecttype=ObjectType.RECORD,
        )
        map_sub0 = ODentry(
            parameter_name="Number of mapped objects",
            index=0x1A00,
            datatype=DataType.UNSIGNED8,
            defaultvalue="0x01",
            accesstype=AccessType.RO,
            parent=od_1a00,
        )
        # 映射到 0x1000:00 (32 bits)
        map_sub1 = ODentry(
            parameter_name="Mapped object 1",
            index=0x1A00,
            datatype=DataType.UNSIGNED32,
            defaultvalue="0x10000020",  # index=0x1000, sub=0x00, bits=32
            accesstype=AccessType.RW,
            parent=od_1a00,
        )
        od_1a00.subobjects[0] = map_sub0
        od_1a00.subobjects[1] = map_sub1
        eds.ods[0x1A00] = od_1a00

        # RX PDO 通信参数 (0x1400)
        od_1400 = ODentry(
            parameter_name="RPDO communication parameter",
            index=0x1400,
            objecttype=ObjectType.RECORD,
        )
        rxsub0 = ODentry(
            parameter_name="Number of entries",
            index=0x1400,
            datatype=DataType.UNSIGNED8,
            defaultvalue="0x02",
            accesstype=AccessType.RO,
            parent=od_1400,
        )
        rxsub1 = ODentry(
            parameter_name="COB-ID",
            index=0x1400,
            datatype=DataType.UNSIGNED32,
            defaultvalue="0x00000200",
            accesstype=AccessType.RW,
            parent=od_1400,
        )
        rxsub2 = ODentry(
            parameter_name="Transmission type",
            index=0x1400,
            datatype=DataType.UNSIGNED8,
            defaultvalue="255",
            accesstype=AccessType.RW,
            parent=od_1400,
        )
        od_1400.subobjects[0] = rxsub0
        od_1400.subobjects[1] = rxsub1
        od_1400.subobjects[2] = rxsub2
        eds.ods[0x1400] = od_1400

        # RX PDO 映射 (0x1600)
        od_1600 = ODentry(
            parameter_name="RPDO mapping",
            index=0x1600,
            objecttype=ObjectType.RECORD,
        )
        rmap0 = ODentry(
            parameter_name="Number of mapped objects",
            index=0x1600,
            datatype=DataType.UNSIGNED8,
            defaultvalue="0x01",
            accesstype=AccessType.RO,
            parent=od_1600,
        )
        rmap1 = ODentry(
            parameter_name="Mapped object 1",
            index=0x1600,
            datatype=DataType.UNSIGNED32,
            defaultvalue="0x10000020",
            accesstype=AccessType.RW,
            parent=od_1600,
        )
        od_1600.subobjects[0] = rmap0
        od_1600.subobjects[1] = rmap1
        eds.ods[0x1600] = od_1600

        # 被映射的对象
        od_1000 = ODentry(
            parameter_name="Device type",
            index=0x1000,
            datatype=DataType.UNSIGNED32,
            defaultvalue="0x00000000",
            accesstype=AccessType.RO,
            pdo_type=PDOMappingType.TPDO,
        )
        eds.ods[0x1000] = od_1000

        return eds

    def test_set_eds(self):
        eds = self._make_eds_with_pdo()
        vm = PDOViewModel()
        vm.set_eds(eds)
        assert vm.eds is eds

    def test_get_tx_slots(self):
        eds = self._make_eds_with_pdo()
        vm = PDOViewModel(eds)
        tx_slots = vm.get_tx_slots()
        assert len(tx_slots) >= 1
        assert tx_slots[0].is_tx is True

    def test_get_rx_slots(self):
        eds = self._make_eds_with_pdo()
        vm = PDOViewModel(eds)
        rx_slots = vm.get_rx_slots()
        assert len(rx_slots) >= 1
        assert rx_slots[0].is_rx is True

    def test_pdo_slot_vm_properties(self):
        eds = self._make_eds_with_pdo()
        vm = PDOViewModel(eds)
        tx_slots = vm.get_tx_slots()
        slot = tx_slots[0]
        assert slot.pdo_type_name == "TX PDO"
        assert slot.config_index_hex == "0x1800"
        assert slot.mapping_index_hex == "0x1A00"

    def test_pdo_mapping_total_bits(self):
        eds = self._make_eds_with_pdo()
        vm = PDOViewModel(eds)
        tx_slots = vm.get_tx_slots()
        # 0x1000:00 映射 32 bits
        assert tx_slots[0].total_bits == 32
        assert not tx_slots[0].is_over_64bit

    def test_pdo_mapping_entries(self):
        eds = self._make_eds_with_pdo()
        vm = PDOViewModel(eds)
        tx_slots = vm.get_tx_slots()
        entries = tx_slots[0].get_mapping_entries()
        assert len(entries) >= 1

    def test_mapping_description(self):
        eds = self._make_eds_with_pdo()
        vm = PDOViewModel(eds)
        tx_slots = vm.get_tx_slots()
        entries = tx_slots[0].get_mapping_entries()
        desc = vm.get_mapping_description(entries[0])
        assert "0x1000" in desc
        assert "bits" in desc

    def test_none_eds(self):
        vm = PDOViewModel(None)
        assert vm.eds is None
        assert vm.get_pdo_slots() == []
        assert vm.get_tx_slots() == []
        assert vm.get_rx_slots() == []
        assert vm.selected_pdo is None

    def test_add_tx_pdo(self):
        eds = self._make_eds_with_pdo()
        vm = PDOViewModel(eds)
        result = vm.add_pdo(rx=False, index=0x1801)
        assert result is True
        assert 0x1801 in eds.ods
        assert 0x1A01 in eds.ods

    def test_add_rx_pdo(self):
        eds = self._make_eds_with_pdo()
        vm = PDOViewModel(eds)
        result = vm.add_pdo(rx=True, index=0x1401)
        assert result is True
        assert 0x1401 in eds.ods
        assert 0x1601 in eds.ods

    def test_add_pdo_invalid_index(self):
        eds = self._make_eds_with_pdo()
        vm = PDOViewModel(eds)
        assert not vm.add_pdo(rx=False, index=0x1000)
        assert not vm.add_pdo(rx=True, index=0x1800)

    def test_add_pdo_duplicate(self):
        eds = self._make_eds_with_pdo()
        vm = PDOViewModel(eds)
        assert not vm.add_pdo(rx=False, index=0x1800)

    def test_find_next_pdo_index(self):
        eds = self._make_eds_with_pdo()
        vm = PDOViewModel(eds)
        assert vm.find_next_pdo_index(rx=False) == 0x1801
        assert vm.find_next_pdo_index(rx=True) == 0x1401

    def test_delete_pdo(self):
        eds = self._make_eds_with_pdo()
        vm = PDOViewModel(eds)
        result = vm.delete_pdo(0x1800)
        assert result is True
        assert 0x1800 not in eds.ods
        assert 0x1A00 not in eds.ods

    def test_add_mapping(self):
        eds = self._make_eds_with_pdo()
        vm = PDOViewModel(eds)
        vm.select_pdo(0)
        result = vm.add_mapping(0x1000, 0, 32)
        assert result is True

    def test_add_mapping_over_64bit(self):
        eds = self._make_eds_with_pdo()
        vm = PDOViewModel(eds)
        vm.select_pdo(0)
        vm.add_mapping(0x1000, 0, 32)
        result = vm.add_mapping(0x1000, 0, 40)
        assert result is False

    def test_delete_mapping(self):
        eds = self._make_eds_with_pdo()
        vm = PDOViewModel(eds)
        vm.select_pdo(0)
        vm.add_mapping(0x1000, 0, 32)
        result = vm.delete_mapping(1)
        assert result is True

    def test_get_mappable_objects(self):
        eds = self._make_eds_with_pdo()
        vm = PDOViewModel(eds)
        mappable = vm.get_mappable_objects()
        assert len(mappable) >= 1
        found_1000 = any(idx == 0x1000 for idx, _, _, _ in mappable)
        assert found_1000


class TestProfileViewModel:
    """ProfileViewModel 测试"""

    def test_scan_profiles(self):
        vm = ProfileViewModel()
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        profile_dir = os.path.join(project_root, "profiles")
        if not os.path.isdir(profile_dir):
            pytest.skip("profiles 目录不存在")

        profiles = vm.scan_profiles(profile_dir)
        assert len(profiles) > 0
        # 至少有一个成功解析的
        valid = [p for p in profiles if p.eds is not None]
        assert len(valid) > 0

    def test_scan_nonexistent_dir(self):
        vm = ProfileViewModel()
        profiles = vm.scan_profiles("/nonexistent/path")
        assert profiles == []

    def test_preview_merge_no_conflict(self):
        target = EDS()
        profile = EDS()
        od = ODentry(
            parameter_name="Test object",
            index=0x2100,
            datatype=DataType.UNSIGNED32,
            defaultvalue="0",
            accesstype=AccessType.RW,
        )
        profile.ods[0x2100] = od

        vm = ProfileViewModel()
        vm.set_target(target)

        info = ProfileInfo(filepath="test.xpd", filename="test.xpd", eds=profile)
        vm.select_profile(info)

        entries = vm.preview_merge(offset=0)
        assert len(entries) == 1
        assert not entries[0].collision
        assert entries[0].insert

    def test_preview_merge_with_conflict(self):
        target = EDS()
        od = ODentry(
            parameter_name="Existing",
            index=0x1000,
            datatype=DataType.UNSIGNED32,
            defaultvalue="0",
            accesstype=AccessType.RO,
        )
        target.ods[0x1000] = od

        profile = EDS()
        od2 = ODentry(
            parameter_name="New Device type",
            index=0x1000,
            datatype=DataType.UNSIGNED32,
            defaultvalue="0x00000000",
            accesstype=AccessType.RO,
        )
        profile.ods[0x1000] = od2

        vm = ProfileViewModel()
        vm.set_target(target)

        info = ProfileInfo(filepath="test.xpd", filename="test.xpd", eds=profile)
        vm.select_profile(info)

        entries = vm.preview_merge(offset=0)
        assert len(entries) == 1
        assert entries[0].collision
        assert not entries[0].insert

    def test_preview_merge_with_offset(self):
        target = EDS()
        profile = EDS()
        od = ODentry(
            parameter_name="Test object",
            index=0x2000,
            datatype=DataType.UNSIGNED32,
            defaultvalue="0",
            accesstype=AccessType.RW,
        )
        profile.ods[0x2000] = od

        vm = ProfileViewModel()
        vm.set_target(target)

        info = ProfileInfo(filepath="test.xpd", filename="test.xpd", eds=profile)
        vm.select_profile(info)

        entries = vm.preview_merge(offset=0x1000)
        assert len(entries) == 1
        assert entries[0].index == 0x3000
        assert not entries[0].collision

    def test_execute_merge(self):
        target = EDS()
        profile = EDS()
        od = ODentry(
            parameter_name="Test object",
            index=0x2100,
            datatype=DataType.UNSIGNED32,
            defaultvalue="0x12345678",
            accesstype=AccessType.RW,
        )
        profile.ods[0x2100] = od

        vm = ProfileViewModel()
        vm.set_target(target)

        info = ProfileInfo(filepath="test.xpd", filename="test.xpd", eds=profile)
        vm.select_profile(info)
        vm.preview_merge(offset=0)

        result = vm.execute_merge(skip_collisions=True)
        assert result is True
        assert 0x2100 in target.ods
        assert target.ods[0x2100].parameter_name == "Test object"

    def test_execute_merge_skip_collision(self):
        target = EDS()
        od = ODentry(
            parameter_name="Existing",
            index=0x1000,
            datatype=DataType.UNSIGNED32,
            defaultvalue="0",
            accesstype=AccessType.RO,
        )
        target.ods[0x1000] = od

        profile = EDS()
        od2 = ODentry(
            parameter_name="New Device type",
            index=0x1000,
            datatype=DataType.UNSIGNED32,
            defaultvalue="0x00000000",
            accesstype=AccessType.RO,
        )
        profile.ods[0x1000] = od2

        vm = ProfileViewModel()
        vm.set_target(target)

        info = ProfileInfo(filepath="test.xpd", filename="test.xpd", eds=profile)
        vm.select_profile(info)
        vm.preview_merge(offset=0)

        result = vm.execute_merge(skip_collisions=True)
        assert result is True
        # 冲突项被跳过，保留原有值
        assert target.ods[0x1000].parameter_name == "Existing"

    def test_toggle_entry(self):
        target = EDS()
        profile = EDS()
        od = ODentry(
            parameter_name="Test",
            index=0x2100,
            datatype=DataType.UNSIGNED32,
            defaultvalue="0",
            accesstype=AccessType.RW,
        )
        profile.ods[0x2100] = od

        vm = ProfileViewModel()
        vm.set_target(target)

        info = ProfileInfo(filepath="test.xpd", filename="test.xpd", eds=profile)
        vm.select_profile(info)
        vm.preview_merge(offset=0)

        assert vm.merge_entries[0].insert is True
        vm.toggle_entry(0x2100, False)
        assert vm.merge_entries[0].insert is False

    def test_get_conflict_count(self):
        target = EDS()
        target.ods[0x1000] = ODentry(parameter_name="Existing", index=0x1000, datatype=DataType.UNSIGNED32, accesstype=AccessType.RO)

        profile = EDS()
        profile.ods[0x1000] = ODentry(parameter_name="Conflict", index=0x1000, datatype=DataType.UNSIGNED32, accesstype=AccessType.RO)
        profile.ods[0x2000] = ODentry(parameter_name="No conflict", index=0x2000, datatype=DataType.UNSIGNED32, accesstype=AccessType.RW)

        vm = ProfileViewModel()
        vm.set_target(target)

        info = ProfileInfo(filepath="test.xpd", filename="test.xpd", eds=profile)
        vm.select_profile(info)
        vm.preview_merge(offset=0)

        assert vm.get_conflict_count() == 1
        assert vm.get_insert_count() == 1
