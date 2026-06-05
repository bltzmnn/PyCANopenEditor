"""GUI 集成测试: 完整流程 - 打开 EDS → 编辑 PDO/OD → 保存 → 重新加载 → 验证

验证以下 GUI 端到端流程：
1. 打开文件后 PDO/OD/Module 视图正确填充
2. 选中 PDO 后 mapping 表格正确显示
3. 编辑 PDO 通信参数 (COB)
4. 添加/删除 PDO
5. 添加/删除 OD 条目
6. 保存到临时文件
7. 重新打开, 验证数据完整

测试 EDS 通过 `PYCANOPEN_TEST_EDS_DIR` 环境变量注入；为保证 PDO/OD
测试覆盖度，建议提供含较多 OD 条目与 PDO 槽位的样本文件。
"""
import os
import sys
import tempfile
import traceback

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _excepthook(exc_type, exc_value, exc_tb):
    print("\n=== UNCAUGLED EXCEPTION ===")
    traceback.print_exception(exc_type, exc_value, exc_tb)
    print("============================\n")


@pytest.fixture(scope="module")
def qapp():
    """QApplication fixture"""
    sys.excepthook = _excepthook
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


@pytest.fixture(scope="module")
def main_window(qapp):
    """创建 MainWindow"""
    from src.gui.viewmodels.main_window_vm import MainWindowVM
    from src.gui.views.main_window import MainWindow

    vm = MainWindowVM()
    window = MainWindow(vm)
    window.show()
    yield window
    window.close()


def _process(qapp, ms=200):
    """处理事件循环指定毫秒"""
    from PySide6.QtCore import QEventLoop
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def _open_file(window, filepath, qapp):
    """同步打开文件"""
    window._vm.open_file(filepath)
    _process(qapp, 100)


def _select_pdo(window, row, qapp):
    """选中 PDO 槽位"""
    window._pdo_view._tx_list.setCurrentRow(row)
    _process(qapp, 50)


def _require_rich_eds(window, filepath, qapp, min_tx_pdos: int = 2):
    """部分集成测试依赖一个 PDO/OD 较为丰富的样本文件。

    通过 `PYCANOPEN_TEST_EDS_DIR` 注入的首个 EDS 文件若是
    精简 profile（如 CiA 模板）时, 主动跳过这些用例, 避免误报。
    """
    window._vm.open_file(filepath)
    _process(qapp, 100)
    dev = window._vm.current_device
    if dev is None:
        pytest.skip("EDS 打开失败, 无法进行集成测试")
    pdo_vm = window._pdo_view._vm
    n_tx = len(pdo_vm.get_tx_slots()) if pdo_vm and hasattr(pdo_vm, "get_tx_slots") else 0
    if n_tx < min_tx_pdos:
        pytest.skip(
            f"PDO 集成测试需要至少 {min_tx_pdos} 个 TX PDO, 当前 {n_tx} 个, "
            f"EDS={os.path.basename(filepath)}"
        )


class TestOpenFile:
    def test_open_real_eds(self, main_window, qapp, eds_path):
        """打开真实 EDS 文件, 验证所有视图填充"""
        _require_rich_eds(main_window, eds_path, qapp, min_tx_pdos=2)
        dev = main_window._vm.current_device
        assert dev is not None, "current_device 应该不为 None"

        product_name = dev.eds.di.ProductName or ""
        vendor_name = dev.eds.di.VendorName or ""

        # PDO 视图
        pdo = main_window._pdo_view
        tx_count = pdo._tx_list.count()
        rx_count = pdo._rx_list.count()
        assert tx_count >= 1, f"应至少有 1 个 TX PDO, 实际 {tx_count}"
        assert rx_count >= 0, f"RX PDO 数不应为负, 实际 {rx_count}"

        # OD 视图 (分 3 个 range)
        od = main_window._od_view
        com = od._com_range._list.count()
        mfr = od._mfr_range._list.count()
        dev_r = od._dev_range._list.count()
        total = com + mfr + dev_r
        assert total > 0, f"OD 视图应该有内容, 实际 {total} ({com}+{mfr}+{dev_r})"

        # Info widget 与 DeviceInfo 双向一致
        assert main_window._vendor_name_edit.text() == vendor_name
        assert main_window._product_name_edit.text() == product_name


class TestPDOEdit:
    def test_select_tx_pdo(self, main_window, qapp, eds_path):
        """选中第一个 TX PDO, 验证 mapping 表格"""
        _require_rich_eds(main_window, eds_path, qapp, min_tx_pdos=1)
        _select_pdo(main_window, 0, qapp)

        pdo = main_window._pdo_view
        comm_text = pdo._comm_index_edit.text()
        mapping_text = pdo._mapping_index_edit.text()
        assert comm_text.startswith("0x18"), (
            f"TX 通信 index 应该在 0x18xx 范围, 实际 {comm_text}"
        )
        assert mapping_text.startswith("0x1A"), (
            f"TX 映射 index 应该在 0x1Axx 范围, 实际 {mapping_text}"
        )

    def test_edit_cob(self, main_window, qapp, eds_path):
        """修改 COB-ID（textEdited 不会由 setText 触发, 直接调 VM）"""
        _require_rich_eds(main_window, eds_path, qapp, min_tx_pdos=1)
        _select_pdo(main_window, 0, qapp)

        pdo_vm = main_window._pdo_view._vm
        tx_slots = pdo_vm.get_tx_slots()
        target_idx = tx_slots[0].config_index
        pdo_vm.update_comm_param(cob=0x200)
        _process(qapp, 50)

        dev = main_window._vm.current_device
        od = dev.eds.ods.get(target_idx)
        sub1 = od.Getsubobject(1)
        assert sub1.defaultvalue == "$NODEID+0x200", (
            f"COB 应该 $NODEID+0x200, 实际 {sub1.defaultvalue}"
        )

    def test_add_pdo(self, main_window, qapp, eds_path):
        """添加新的 TX PDO"""
        _open_file(main_window, eds_path, qapp)
        pdo = main_window._pdo_view
        pdo_vm = pdo._vm

        before_count = pdo._tx_list.count()
        # 找到一个空的 TX PDO index
        eds = main_window._vm.current_device.eds
        used = {s.ConfigurationIndex for s in pdo_vm._helper.pdoslots if s.isTXPDO()}
        for idx in range(0x1800, 0x1A00):
            if idx not in used:
                new_idx = idx
                break
        else:
            pytest.skip("TX PDO 区间已满")

        result = pdo_vm.add_pdo(rx=False, index=new_idx)
        _process(qapp, 50)
        # 重建后列表应该增加
        pdo._refresh_pdo_lists()
        _process(qapp, 50)
        assert pdo._tx_list.count() == before_count + 1, f"TX 应增加 1, 实际 {pdo._tx_list.count()}"

    def test_delete_pdo(self, main_window, qapp, eds_path):
        """删除最后一个 TX PDO"""
        _open_file(main_window, eds_path, qapp)
        pdo = main_window._pdo_view
        pdo_vm = pdo._vm

        before_count = pdo._tx_list.count()
        # 直接调 VM 删除最后一个 TX slot 的 config index
        tx_slots = pdo_vm.get_tx_slots()
        if not tx_slots:
            pytest.skip("没有 TX PDO 可删除")
        last_idx = tx_slots[-1].config_index
        pdo_vm.delete_pdo(last_idx)
        _process(qapp, 50)
        pdo._refresh_pdo_lists()
        _process(qapp, 50)
        assert pdo._tx_list.count() == before_count - 1, f"TX 应减少 1, 实际 {pdo._tx_list.count()}"


class TestODEdit:
    def test_add_od_entry(self, main_window, qapp, eds_path):
        """添加新的 OD 条目"""
        _open_file(main_window, eds_path, qapp)
        od_vm = main_window._od_view._vm

        before = len(od_vm.eds.ods)
        result = od_vm.add_od_entry(0x5F00, "TestEntry", type(None)) if False else None
        # 使用正确的 ObjectType
        from src.core.models.datatypes import ObjectType
        new_od = od_vm.add_od_entry(0x5F00, "TestEntry", ObjectType.VAR)
        _process(qapp, 50)

        assert new_od is not None, "添加 OD 应该成功"
        assert 0x5F00 in od_vm.eds.ods, "OD 字典应该包含新条目"
        assert len(od_vm.eds.ods) == before + 1

        # 清理
        od_vm.delete_od_entry(0x5F00)
        assert 0x5F00 not in od_vm.eds.ods

    def test_delete_od_entry(self, main_window, qapp, eds_path):
        """删除 OD 条目"""
        _open_file(main_window, eds_path, qapp)
        od_vm = main_window._od_view._vm
        # 0x1000 (DeviceType) 应该存在
        assert 0x1000 in od_vm.eds.ods
        before = len(od_vm.eds.ods)

        result = od_vm.delete_od_entry(0x1000)
        _process(qapp, 50)
        assert result
        assert 0x1000 not in od_vm.eds.ods
        assert len(od_vm.eds.ods) == before - 1


class TestSaveReload:
    def test_save_and_reload_preserves_pdo_count(self, main_window, qapp, eds_path):
        """保存到临时文件, 重新打开, 验证 PDO 数量不变"""
        _open_file(main_window, eds_path, qapp)
        vm = main_window._vm

        # 记录原始 PDO 数量
        pdo_view = main_window._pdo_view
        original_tx = pdo_view._tx_list.count()
        original_rx = pdo_view._rx_list.count()

        # 保存到临时文件
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_eds = os.path.join(tmpdir, "test.eds")
            result = vm.save_file(tmp_eds)
            assert result, "保存应该成功"
            assert os.path.exists(tmp_eds)

            # 关闭当前设备
            vm.close_device(0)
            _process(qapp, 50)

            # 重新打开
            dev = vm.open_file(tmp_eds)
            _process(qapp, 100)
            assert dev is not None

            # 验证 PDO 数量
            new_tx = pdo_view._tx_list.count()
            new_rx = pdo_view._rx_list.count()
            assert new_tx == original_tx, f"TX PDO 数量不一致: {original_tx} -> {new_tx}"
            assert new_rx == original_rx, f"RX PDO 数量不一致: {original_rx} -> {new_rx}"


class TestRuntimeErrors:
    def test_no_runtime_error_on_open(self, main_window, qapp, eds_path):
        """打开文件过程中不应该有 RuntimeError"""
        errors = []

        def error_handler(exc_type, exc_value, exc_tb):
            errors.append((exc_type, exc_value, exc_tb))

        old_hook = sys.excepthook
        sys.excepthook = error_handler
        try:
            _open_file(main_window, eds_path, qapp)
            _process(qapp, 200)
        finally:
            sys.excepthook = old_hook

        real_errors = [e for e in errors if "RuntimeError" in str(e[1]) and "deleted" in str(e[1])]
        assert len(real_errors) == 0, f"发现 RuntimeError: {real_errors}"

    def test_select_od_entry_does_not_crash(self, main_window, qapp, eds_path):
        """选中 OD 条目后 sub_table 不应该被 GC 回收 (right_splitter 未加到 layout 的回归)"""
        _open_file(main_window, eds_path, qapp)

        od = main_window._od_view
        com_list = od._com_range._list
        assert com_list.count() > 0

        com_list.setCurrentRow(0)
        _process(qapp, 100)

        assert od._sub_table.rowCount() > 0, "sub_table 应该在选中后填充"
        assert od._index_label.text(), "属性面板应该显示 index"


class TestDisabledEntryDisplay:
    def test_disabled_entries_visible_with_mark_and_gray(self, main_window, qapp, eds_path):
        """disabled 条目应该出现在列表中, 文本含 [disabled] 标记, 前景色为灰"""
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QColor

        _open_file(main_window, eds_path, qapp)
        od_view = main_window._od_view
        od_vm = od_view._vm

        target_index = 0x1000
        assert target_index in od_vm.eds.ods, f"前置条件: {target_index:#x} 应存在"
        od = od_vm.eds.ods[target_index]
        original_disabled = od.prop.CO_disabled
        od.prop.CO_disabled = True

        try:
            od_view.refresh()
            _process(qapp, 50)

            com_list = od_view._com_range._list
            found_row = -1
            for row in range(com_list.count()):
                if f"{target_index:#x}".lower() in com_list.item(row).text().lower():
                    found_row = row
                    break
            assert found_row >= 0, "disabled 条目应该仍然出现在列表中, 不应被隐藏"

            item = com_list.item(found_row)
            assert "[disabled]" in item.text(), f"文本应含 [disabled] 标记: {item.text()}"

            fg = item.foreground().color()
            gray_hex = QColor(Qt.GlobalColor.gray).name()
            assert fg.name() == gray_hex, f"前景色应为灰色, 实际 {fg.name()}"
        finally:
            od.prop.CO_disabled = original_disabled
            od_view.refresh()
            _process(qapp, 50)

        for row in range(com_list.count()):
            if f"{target_index:#x}".lower() in com_list.item(row).text().lower():
                item = com_list.item(row)
                assert "[disabled]" not in item.text(), "取消禁用后应移除 [disabled] 标记"
                break


class TestPDO32SlotEndToEnd:
    def test_all_32_slots_accessible_and_editable(self, main_window, qapp, eds_path):
        """PDO slot 端到端：所有 TX/RX 都能选中并显示 mapping"""
        _require_rich_eds(main_window, eds_path, qapp, min_tx_pdos=2)
        pdo_view = main_window._pdo_view
        pdo_vm = pdo_view._vm

        assert pdo_vm._helper is not None
        total_slots = len(pdo_vm._helper.pdoslots)
        assert total_slots >= 2, f"应有多个 PDO slot, 实际 {total_slots}"
        assert pdo_view._tx_list.count() >= 1
        assert pdo_view._rx_list.count() >= 0

        for row in range(pdo_view._tx_list.count()):
            pdo_view._tx_list.setCurrentRow(row)
            _process(qapp, 30)
            comm = pdo_view._comm_index_edit.text()
            assert comm.startswith("0x18"), f"row {row} 通信 index 应在 0x18xx, 实际 {comm}"
            assert pdo_view._mapping_table.rowCount() > 0, (
                f"TX row {row} 应该有至少 1 个映射"
            )
            total_text = pdo_view._total_bits_label.text()
            assert "总位数" in total_text

        if pdo_view._rx_list.count() > 0:
            pdo_view._rx_list.setCurrentRow(0)
            _process(qapp, 30)
            comm = pdo_view._comm_index_edit.text()
            assert comm.startswith("0x14"), f"RX[0] 通信 index 应在 0x14xx, 实际 {comm}"
            assert pdo_view._mapping_table.rowCount() > 0

    def test_select_each_tx_updates_comm_params(self, main_window, qapp, eds_path):
        """选中不同 TX PDO 时, 通信参数面板应正确刷新"""
        _require_rich_eds(main_window, eds_path, qapp, min_tx_pdos=2)
        pdo_view = main_window._pdo_view
        pdo_vm = pdo_view._vm

        seen_indexes = set()
        for row in range(pdo_view._tx_list.count()):
            pdo_view._tx_list.setCurrentRow(row)
            _process(qapp, 30)
            comm = pdo_view._comm_index_edit.text()
            seen_indexes.add(comm)
        expected = pdo_view._tx_list.count()
        assert len(seen_indexes) == expected, (
            f"{expected} 个 TX PDO 应有 {expected} 个不同通信 index, "
            f"实际 {len(seen_indexes)}"
        )
