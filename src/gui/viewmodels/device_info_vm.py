"""Device Info ViewModel"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QObject, Signal

from ...core.models.eds import EDS


class DeviceInfoVM(QObject):
    """Device Info 面板 ViewModel，绑定 EDS 的 DeviceInfo"""
    field_changed = Signal(str, str)

    def __init__(self, eds: Optional[EDS] = None, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._eds = eds

    @property
    def eds(self) -> Optional[EDS]:
        return self._eds

    @eds.setter
    def eds(self, value: EDS) -> None:
        self._eds = value

    def _get(self, attr: str) -> str:
        if self._eds is None:
            return ""
        return str(getattr(self._eds.di, attr, ""))

    def _set(self, attr: str, value: str) -> None:
        if self._eds is None:
            return
        setattr(self._eds.di, attr, value)
        self._eds.Dirty = True

    @property
    def vendor_name(self) -> str:
        return self._get("VendorName")

    @vendor_name.setter
    def vendor_name(self, v: str) -> None:
        self._set("VendorName", v)

    @property
    def vendor_number(self) -> str:
        return self._get("VendorNumber")

    @vendor_number.setter
    def vendor_number(self, v: str) -> None:
        self._set("VendorNumber", v)

    @property
    def product_name(self) -> str:
        return self._get("ProductName")

    @product_name.setter
    def product_name(self, v: str) -> None:
        self._set("ProductName", v)

    @property
    def product_number(self) -> str:
        return self._get("ProductNumber")

    @product_number.setter
    def product_number(self, v: str) -> None:
        self._set("ProductNumber", v)

    @property
    def revision_number(self) -> str:
        return self._get("RevisionNumber")

    @revision_number.setter
    def revision_number(self, v: str) -> None:
        self._set("RevisionNumber", v)

    @property
    def granularity(self) -> str:
        return self._get("Granularity")

    @granularity.setter
    def granularity(self, v: str) -> None:
        self._set("Granularity", v)
