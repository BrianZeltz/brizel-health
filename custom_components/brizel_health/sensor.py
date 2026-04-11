"""Sensor platform forwarding for Brizel Health."""

from .adapters.homeassistant.entities.sensor import async_setup_entry

__all__ = ["async_setup_entry"]
