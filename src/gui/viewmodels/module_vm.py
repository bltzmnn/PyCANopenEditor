"""Module 视图 ViewModel"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ...core.models.eds import EDS
from ...core.models.info_section import Module as ModuleData


@dataclass
class ModuleItemVM:
    module_index: int
    product_name: str
    product_version: int
    product_revision: int
    order_code: str
    is_connected: bool = False


@dataclass
class ModuleSubExtendVM:
    od_index: int
    od_name: str
    is_found: bool = True


class ModuleViewModel:
    def __init__(self) -> None:
        self._eds: Optional[EDS] = None
        self.modules: list[ModuleItemVM] = []
        self.sub_extends: list[ModuleSubExtendVM] = []
        self.module_comments: list[str] = []
        self.nr_supported: int = 0
        self._selected_module_index: Optional[int] = None

    def set_eds(self, eds: Optional[EDS]) -> None:
        self._eds = eds
        self.refresh()

    def refresh(self) -> None:
        self.modules.clear()
        self.sub_extends.clear()
        self.module_comments.clear()
        self._selected_module_index = None

        if self._eds is None:
            self.nr_supported = 0
            return

        self.nr_supported = self._eds.sm.NrOfEntries
        connected_keys = set(self._eds.cm.connectedmodulelist.keys())

        for mod_index, mod in sorted(self._eds.modules.items()):
            mi = mod.mi
            self.modules.append(ModuleItemVM(
                module_index=mod_index,
                product_name=mi.ProductName if mi else "",
                product_version=mi.ProductVersion if mi else 0,
                product_revision=mi.ProductRevision if mi else 0,
                order_code=mi.OrderCode if mi else "",
                is_connected=mod_index in connected_keys,
            ))

    def select_module(self, module_index: int) -> None:
        if self._eds is None or module_index not in self._eds.modules:
            self.sub_extends.clear()
            self.module_comments.clear()
            self._selected_module_index = None
            return

        self._selected_module_index = module_index
        mod = self._eds.modules[module_index]
        self.sub_extends.clear()
        self.module_comments.clear()

        if mod.mse is not None:
            for od_index in mod.mse.objectlist.values():
                if od_index in self._eds.ods:
                    od_name = self._eds.ods[od_index].parameter_name
                    self.sub_extends.append(ModuleSubExtendVM(
                        od_index=od_index,
                        od_name=od_name,
                        is_found=True,
                    ))
                elif od_index in mod.modulesubext:
                    sub_od = mod.modulesubext[od_index]
                    od_name = getattr(sub_od, 'parameter_name', f'Unknown 0x{od_index:04X}')
                    self.sub_extends.append(ModuleSubExtendVM(
                        od_index=od_index,
                        od_name=od_name,
                        is_found=False,
                    ))
                else:
                    self.sub_extends.append(ModuleSubExtendVM(
                        od_index=od_index,
                        od_name="** OD NOT FOUND **",
                        is_found=False,
                    ))

        if mod.mc is not None:
            self.module_comments = list(mod.mc.comments)
