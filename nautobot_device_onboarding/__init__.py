"""App declaration for nautobot_device_onboarding."""

# Metadata is inherited from Nautobot. If not including Nautobot in the environment, this should be added
from importlib import metadata

from nautobot.apps import NautobotAppConfig

__version__ = metadata.version(__name__)


class NautobotDeviceOnboardingConfig(NautobotAppConfig):
    """App configuration for the nautobot_device_onboarding app."""

    name = "nautobot_device_onboarding"
    verbose_name = "Device Onboarding"
    version = __version__
    author = "Network to Code, LLC"
    description = "Device Onboarding."
    base_url = "nautobot-device-onboarding"
    required_settings = []
    min_version = "2.0.3"
    max_version = "2.9999"
    default_settings = {}
    caching_config = {}


config = NautobotDeviceOnboardingConfig  # pylint:disable=invalid-name
