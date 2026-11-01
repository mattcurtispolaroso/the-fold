"""Item system — Module 5a.

Public API: ItemRegistry, ItemManager, load_item_registry.
"""
from src.systems.items.registry import ItemRegistry, load_item_registry
from src.systems.items.manager import ItemManager

__all__ = ["ItemRegistry", "ItemManager", "load_item_registry"]
