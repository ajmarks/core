"""Oven state representation."""

import asyncio
from typing import Any, Dict, List, Optional, Type
from gekitchen import (
    ErdCode,
    ErdCodeType,
    ErdApplianceType,
    ErdMeasurementUnits,
    GeAppliance,
    OvenConfiguration,
    translate_erd_code
)
from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.helpers.entity import Entity

from .const import DOMAIN

TEMPERATURE_ERD_CODES = {
    ErdCode.HOT_WATER_SET_TEMP,
    ErdCode.LOWER_OVEN_DISPLAY_TEMPERATURE,
    ErdCode.LOWER_OVEN_PROBE_DISPLAY_TEMP,
    ErdCode.LOWER_OVEN_USER_TEMP_OFFSET,
    ErdCode.LOWER_OVEN_RAW_TEMPERATURE,
    ErdCode.OVEN_MODE_MIN_MAX_TEMP,
    ErdCode.UPPER_OVEN_DISPLAY_TEMPERATURE,
    ErdCode.UPPER_OVEN_PROBE_DISPLAY_TEMP,
    ErdCode.UPPER_OVEN_USER_TEMP_OFFSET,
    ErdCode.UPPER_OVEN_RAW_TEMPERATURE,
}


def get_appliance_api_type(appliance_type: ErdApplianceType) -> Type:
    """Get the appropriate appliance type"""
    if appliance_type == ErdApplianceType.OVEN:
        return OvenApi
    # Fallback
    return ApplianceApi


def stringify_erd_value(erd_code: ErdCodeType, value: Any) -> Optional[str]:
    """
    Convert an erd property value to a nice string

    :param erd_code:
    :param value: The current value in its native format
    :return: The value converted to a string
    """
    if value is None:
        return None

    erd_code = translate_erd_code(erd_code)
    if erd_code == ErdCode.CLOCK_TIME:
        return value.strftime('%H:%M:%S')
    return str(value)


def get_erd_units(erd_code: ErdCodeType, measurement_units: ErdMeasurementUnits):
    erd_code = translate_erd_code(erd_code)
    if not measurement_units:
        return None

    if erd_code in TEMPERATURE_ERD_CODES:
        if measurement_units == ErdMeasurementUnits.METRIC:
            return TEMP_CELSIUS
        return TEMP_FAHRENHEIT
    return None


class ApplianceApi:
    """
    API class to represent a single physical device.

    Since a physical device can have many entities, we'll pool common elements here
    """
    APPLIANCE_TYPE = None  # type: Optional[ErdApplianceType]

    def __init__(self, appliance: GeAppliance):
        if not appliance.initialized:
            raise RuntimeError('Appliance not ready')
        self._appliance = appliance
        self._loop = appliance.client.loop
        self.initial_update = False
        self._entities = {}  # type: Optional[Dict[str, Entity]]

    @property
    def loop(self) -> Optional[asyncio.AbstractEventLoop]:
        if self._loop is None:
            self._loop = self._appliance.client.loop
        return self._loop

    @property
    def appliance(self) -> GeAppliance:
        return self._appliance

    @property
    def serial_number(self) -> str:
        return self.appliance.get_erd_value(ErdCode.SERIAL_NUMBER)

    @property
    def model_number(self) -> str:
        return self.appliance.get_erd_value(ErdCode.MODEL_NUMBER)

    @property
    def name(self) -> str:
        return f"GE Appliance {self.serial_number}"

    @property
    def device_info(self) -> Dict:
        """Device info dictionary."""
        return {
            "identifiers": {(DOMAIN, self.serial_number)},
            "name": self.name,
            "manufacturer": "GE",
            "model": self.model_number
        }

    @property
    def entities(self) -> List[Entity]:
        return list(self._entities.values())

    def get_all_entities(self) -> List[Entity]:
        """Create Entities for this device."""
        entities = [
            GeSensor(self, ErdCode.CLOCK_TIME),
            GeBinarySensor(self, ErdCode.SABBATH_MODE),
        ]
        return entities

    def build_entities_list(self) -> None:
        """Build the entities list, adding anything new."""
        entities = self.get_all_entities()
        for entity in entities:
            if entity.unique_id not in self._entities:
                self._entities[entity.unique_id] = entity


class OvenApi(ApplianceApi):
    """API class for oven objects"""
    APPLIANCE_TYPE = ErdApplianceType.OVEN

    def get_all_entities(self) -> List[Entity]:
        base_entities = super().get_all_entities()
        oven_config = self.appliance.get_erd_value(ErdCode.OVEN_CONFIGURATION)  # type: OvenConfiguration
        oven_entities = [
            GeSensor(self, ErdCode.UPPER_OVEN_COOK_MODE),
            GeSensor(self, ErdCode.UPPER_OVEN_COOK_TIME_REMAINING),
            GeSensor(self, ErdCode.UPPER_OVEN_CURRENT_STATE),
            GeSensor(self, ErdCode.UPPER_OVEN_DELAY_TIME_REMAINING),
            GeSensor(self, ErdCode.UPPER_OVEN_DISPLAY_TEMPERATURE),
            GeSensor(self, ErdCode.UPPER_OVEN_ELAPSED_COOK_TIME),
            GeSensor(self, ErdCode.UPPER_OVEN_KITCHEN_TIMER),
            GeSensor(self, ErdCode.UPPER_OVEN_PROBE_DISPLAY_TEMP),
            GeSensor(self, ErdCode.UPPER_OVEN_USER_TEMP_OFFSET),
            GeSensor(self, ErdCode.UPPER_OVEN_RAW_TEMPERATURE),
            GeBinarySensor(self, ErdCode.UPPER_OVEN_PROBE_PRESENT),
            GeBinarySensor(self, ErdCode.UPPER_OVEN_REMOTE_ENABLED),
        ]

        if oven_config.has_lower_oven:
            oven_entities.extend([
                GeSensor(self, ErdCode.UPPER_OVEN_COOK_MODE),
                GeSensor(self, ErdCode.UPPER_OVEN_COOK_TIME_REMAINING),
                GeSensor(self, ErdCode.UPPER_OVEN_CURRENT_STATE),
                GeSensor(self, ErdCode.UPPER_OVEN_DELAY_TIME_REMAINING),
                GeSensor(self, ErdCode.UPPER_OVEN_DISPLAY_TEMPERATURE),
                GeSensor(self, ErdCode.UPPER_OVEN_ELAPSED_COOK_TIME),
                GeSensor(self, ErdCode.UPPER_OVEN_KITCHEN_TIMER),
                GeSensor(self, ErdCode.UPPER_OVEN_PROBE_DISPLAY_TEMP),
                GeSensor(self, ErdCode.UPPER_OVEN_USER_TEMP_OFFSET),
                GeSensor(self, ErdCode.UPPER_OVEN_RAW_TEMPERATURE),
                GeBinarySensor(self, ErdCode.UPPER_OVEN_PROBE_PRESENT),
                GeBinarySensor(self, ErdCode.UPPER_OVEN_REMOTE_ENABLED),
            ])
        return base_entities + oven_entities


class GeEntity(Entity):
    """Base class for all GE Entities"""
    def __init__(self, api: ApplianceApi):
        appliance = api.appliance
        self._api = api
        self._appliance = appliance

    @property
    def api(self) -> ApplianceApi:
        return self._api

    @property
    def device_info(self) -> Optional[Dict[str, Any]]:
        return self.api.device_info

    @property
    def serial_number(self):
        return self.api.serial_number

    @property
    def should_poll(self) -> bool:
        """Don't poll."""
        return False

    @property
    def available(self) -> bool:
        return self.appliance.available

    @property
    def appliance(self) -> GeAppliance:
        return self._appliance

    @property
    def unique_id(self) -> Optional[str]:
        raise NotImplementedError

    @property
    def name(self) -> Optional[str]:
        raise NotImplementedError


class GeErdEntity(GeEntity):
    """Parent class for GE entities tied to a specific ERD"""
    def __init__(self, api: ApplianceApi, erd_code: ErdCodeType):
        super().__init__(api)
        self._erd_code = translate_erd_code(erd_code)

    @property
    def erd_code(self) -> ErdCodeType:
        return self._erd_code

    @property
    def erd_string(self) -> str:
        erd_code = self.erd_code
        if isinstance(self.erd_code, ErdCode):
            return erd_code.name
        return erd_code

    @property
    def name(self) -> Optional[str]:
        erd_string = self.erd_string
        return ' '.join(erd_string.split('_')).title()

    @property
    def unique_id(self) -> Optional[str]:
        return f'{DOMAIN}_{self.serial_number}_{self.erd_string.lower()}'


class GeSensor(GeErdEntity):
    """GE Entity for sensors"""
    @property
    def state(self) -> Optional[str]:
        value = self.appliance.get_erd_value(self.erd_code)
        return stringify_erd_value(self.erd_code, value)

    @property
    def measurement_system(self) -> Optional[ErdMeasurementUnits]:
        return self._appliance.get_erd_value(ErdCode.TEMPERATURE_UNIT)

    @property
    def units(self) -> Optional[str]:
        return get_erd_units(self.erd_code, self.measurement_system)


class GeBinarySensor(GeErdEntity):
    @property
    def is_on(self) -> bool:
        return bool(self.appliance.get_erd_value(self.erd_code))
