"""
Abstract Base Class for DDC/CI display controllers.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class DDCController(ABC):
    """Base interface for platform-specific DDC/CI hardware controllers."""

    @abstractmethod
    def list_displays(self) -> List[Dict[str, Any]]:
        """
        Enumerate all connected physical displays.
        Returns a list of dicts with keys: 'id', 'name', 'index', etc.
        """
        pass

    @abstractmethod
    def set_input_source(self, display_index: int, input_value: int) -> bool:
        """
        Send VESA VCP Code 0x60 (Input Source Select) to the specified display.
        :param display_index: Physical index of the display (0-indexed).
        :param input_value: VCP input code (e.g. 15=DP1, 16=DP2, 17=HDMI1, 18=HDMI2, 27=Type-C).
        :return: True if the command succeeded, False otherwise.
        """
        pass

    @abstractmethod
    def get_input_source(self, display_index: int) -> Optional[int]:
        """
        Query current VESA VCP Code 0x60 (Input Source) if supported.
        :param display_index: Physical index of the display.
        :return: Current VCP code integer, or None if unsupported/dormant.
        """
        pass
