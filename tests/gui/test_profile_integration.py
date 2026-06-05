"""Profile 导入 GUI 集成测试

使用仓库自带的 `profiles/` 目录下的 XPD 文件，验证：
1. ProfileDialog 能正确扫描和列出 XPD 文件
2. 选择 profile 后能预览合并
3. 冲突能被正确检测和显示
4. 执行合并后 OD 条目被正确导入

测试 EDS 通过 `PYCANOPEN_TEST_EDS_DIR` 环境变量注入。
"""
import os
import sys
import tempfile
import traceback

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QDialog


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


PROFILE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "profiles")
)


def _excepthook(exc_type, exc_value, exc_tb):
    print("\n=== UNCAUGLED EXCEPTION ===")
    traceback.print_exception(exc_type, exc_value, exc_tb)
    print("============================\n")


@pytest.fixture(scope="module")
def qapp():
    sys.excepthook = _excepthook
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


@pytest.fixture(scope="module")
def main_window(qapp):
    from src.gui.viewmodels.main_window_vm import MainWindowVM
    from src.gui.views.main_window import MainWindow

    vm = MainWindowVM()
    window = MainWindow(vm)
    window.show()
    yield window
    window.close()


def _process(qapp, ms=200):
    from PySide6.QtCore import QEventLoop
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def _open_file(window, filepath, qapp):
    window._vm.open_file(filepath)
    _process(qapp, 100)


class TestProfileDialog:
    def test_dialog_loads_profiles(self, main_window, qapp, eds_path):
        """ProfileDialog 能扫描和列出 profile 目录中的 XPD 文件"""
        from src.gui.viewmodels.profile_vm import ProfileViewModel
        from src.gui.views.profile_view import ProfileDialog

        _open_file(main_window, eds_path, qapp)
        dev = main_window._vm.current_device

        vm = ProfileViewModel()
        dialog = ProfileDialog(vm, dev.eds, PROFILE_DIR, main_window)
        _process(qapp, 100)

        assert dialog._profile_list.count() > 0, "应该扫描到至少一个 profile"
        # 至少应该有 DS301_profile.xpd
        items_text = [dialog._profile_list.item(i).text() for i in range(dialog._profile_list.count())]
        assert any("DS301" in t for t in items_text), f"应该包含 DS301 profile, 实际: {items_text}"

    def test_profile_select_triggers_preview(self, main_window, qapp, eds_path):
        """选择 profile 后能预览合并"""
        from src.gui.viewmodels.profile_vm import ProfileViewModel
        from src.gui.views.profile_view import ProfileDialog

        _open_file(main_window, eds_path, qapp)
        dev = main_window._vm.current_device

        vm = ProfileViewModel()
        dialog = ProfileDialog(vm, dev.eds, PROFILE_DIR, main_window)
        _process(qapp, 100)

        assert dialog._profile_list.count() > 0
        dialog._profile_list.setCurrentRow(0)
        _process(qapp, 100)

        # 选中后 merge_table 应该被填充
        assert dialog._merge_table.rowCount() > 0, "merge_table 应该被填充"
        # 导入按钮应该被启用
        assert dialog._import_btn.isEnabled(), "导入按钮应该启用"

    def test_conflict_detection(self, main_window, qapp, eds_path):
        """冲突能被正确检测和标记"""
        from src.gui.viewmodels.profile_vm import ProfileViewModel
        from src.gui.views.profile_view import ProfileDialog

        _open_file(main_window, eds_path, qapp)
        dev = main_window._vm.current_device

        vm = ProfileViewModel()
        dialog = ProfileDialog(vm, dev.eds, PROFILE_DIR, main_window)
        _process(qapp, 100)

        # 样本 EDS 通常已经包含 0x1000-0x1FFF 范围的 OD 条目
        # DS301_profile.xpd 也包含 0x1000-0x1FFF 范围的条目
        # 所以应该有冲突
        dialog._profile_list.setCurrentRow(0)  # DS301
        _process(qapp, 100)

        # 检查 conflict_label 文本
        conflict_text = dialog._conflict_label.text()
        assert "冲突" in conflict_text, f"应该显示冲突信息, 实际: {conflict_text}"
        # 至少有一些冲突（因为有重叠的 0x1000-0x1FFF 范围）
        assert vm.get_conflict_count() > 0, f"应该有冲突, 实际 0"

    def test_offset_shifts_indexes(self, main_window, qapp, eds_path):
        """设置 offset 应该使所有 index 偏移（十进制和十六进制都支持）"""
        from src.gui.viewmodels.profile_vm import ProfileViewModel
        from src.gui.views.profile_view import ProfileDialog

        _open_file(main_window, eds_path, qapp)
        dev = main_window._vm.current_device

        vm = ProfileViewModel()
        dialog = ProfileDialog(vm, dev.eds, PROFILE_DIR, main_window)
        _process(qapp, 100)

        dialog._profile_list.setCurrentRow(0)
        _process(qapp, 100)

        if not vm.merge_entries:
            pytest.skip("没有可合并条目")
        original_first_idx = vm.merge_entries[0].index

        dialog._offset_edit.setText("8192")
        dialog._on_preview()
        _process(qapp, 100)
        assert vm.merge_entries[0].index == original_first_idx + 0x2000, (
            f"十进制 offset 失败: {vm.merge_entries[0].index:#x}"
        )

        dialog._offset_edit.setText("0x4000")
        dialog._on_preview()
        _process(qapp, 100)
        assert vm.merge_entries[0].index == original_first_idx + 0x4000, (
            f"十六进制 offset 失败: {vm.merge_entries[0].index:#x}"
        )

    def test_execute_merge_imports_entries(self, main_window, qapp, eds_path):
        """执行合并后 OD 条目被正确导入到目标设备"""
        from src.gui.viewmodels.profile_vm import ProfileViewModel
        from src.gui.views.profile_view import ProfileDialog

        _open_file(main_window, eds_path, qapp)
        dev = main_window._vm.current_device
        eds = dev.eds

        # 记录原始 OD 数量
        before_count = len(eds.ods)

        vm = ProfileViewModel()
        dialog = ProfileDialog(vm, eds, PROFILE_DIR, main_window)
        _process(qapp, 100)

        # 用偏移避开冲突
        dialog._profile_list.setCurrentRow(0)
        _process(qapp, 100)
        dialog._offset_edit.setText("0x4000")  # 用厂商区之外的偏移
        dialog._on_preview()
        _process(qapp, 100)

        # 取消所有冲突的项
        dialog._on_deselect_conflicts()
        _process(qapp, 100)

        # 执行合并
        result = vm.execute_merge(skip_collisions=True)
        _process(qapp, 100)
        assert result, "合并应该成功"

        # 验证有新条目被导入
        after_count = len(eds.ods)
        assert after_count > before_count, (
            f"OD 数量应该增加: {before_count} -> {after_count}"
        )

    def test_merge_skips_collisions(self, main_window, qapp, eds_path):
        """冲突的项应该被跳过, 保留原有值"""
        from src.gui.viewmodels.profile_vm import ProfileViewModel
        from src.gui.views.profile_view import ProfileDialog

        _open_file(main_window, eds_path, qapp)
        dev = main_window._vm.current_device
        eds = dev.eds

        # 记录 0x1000 的原始值
        original_name = eds.ods[0x1000].parameter_name
        original_value = eds.ods[0x1000].defaultvalue

        vm = ProfileViewModel()
        dialog = ProfileDialog(vm, eds, PROFILE_DIR, main_window)
        _process(qapp, 100)

        # 选 profile 不设偏移, 0x1000 必然冲突
        dialog._profile_list.setCurrentRow(0)
        _process(qapp, 100)

        # 取消所有冲突的项
        dialog._on_deselect_conflicts()
        _process(qapp, 100)

        # 执行合并
        vm.execute_merge(skip_collisions=True)
        _process(qapp, 100)

        # 验证 0x1000 保留原值
        assert eds.ods[0x1000].parameter_name == original_name
        assert eds.ods[0x1000].defaultvalue == original_value
